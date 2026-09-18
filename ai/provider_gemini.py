"""
Cybzenor - Google Gemini AI Sağlayıcısı
google-genai SDK ile Structured Output (TargetProfile) dönüşümü ve kural tabanlı fallback mekanizması.
"""

import os
import re
import json
import logging
import time
from typing import Optional
from config.settings import settings
from utils.logger import logger
from ai.base import BaseAIProvider
from ai.schemas import TargetProfile
from ai.local_llm_engine import local_llm_engine
from utils.platform_helper import print_info

# google-genai SDK'sı, "AFC kullanmayın" gibi kendi iç bilgilendirme uyarılarını
# doğrudan konsola basar; kullanıcıya teknik gürültü olarak yansımaması için susturuyoruz.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

# Süreç genelinde PAYLAŞILAN devre kesici durumu: main.py ve RankingEngine gibi farklı
# yerler ayrı ayrı GeminiAIProvider() nesneleri oluşturuyor. Bu bayrak nesne-bazlı olsaydı
# (instance attribute), bir kesinti sırasında her yeni provider nesnesi Gemini'yi sıfırdan
# tekrar deneyip zaman kaybettirirdi. Süreleri sınırlı tutuyoruz (kalıcı değil) ki geçici
# bir kesinti düzeldiğinde birkaç dakika sonraki farklı bir işlem yine Gemini'yi deneyebilsin.
_DOWN_COOLDOWN_SECONDS = 60
_provider_state = {"gemini_down_until": 0.0, "local_llm_down_until": 0.0}

_TR_ASCII_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _normalize_tr(text: str) -> str:
    """Türkçe karakterleri ASCII karşılıklarına çevirir (sözlük anahtar eşleşmesi için)."""
    return text.translate(_TR_ASCII_MAP)


class GeminiAIProvider(BaseAIProvider):
    """Google Gemini modellerini kullanarak OSINT verisini yapılandıran sağlayıcı."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest") -> None:
        key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        super().__init__(api_key=key)
        self.model_name = model_name
        self._client = None
        self.client_init_error: Optional[str] = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                # Bu, tekrar eden bir istek hatası değil — istemci hiç kurulamadı demektir
                # (bozuk anahtar formatı, SDK sorunu vb.). Sessiz kalırsa kullanıcı "Gemini
                # Aktif" sanıp hiç fark etmeden offline motorla çalışmaya devam eder.
                self.client_init_error = str(e)
                logger.warning(f"Google GenAI istemcisi başlatılamadı: {e}")

    def is_available(self) -> bool:
        """API anahtarı ve istemci geçerli mi (ve şu an süreç genelinde 'düşmüş' değil mi)?"""
        return bool(self._client and self.api_key) and time.time() >= _provider_state["gemini_down_until"]

    def _cascade(self, gemini_fn, local_fn, fallback_fn, label: str):
        """
        Üç katmanlı yedekleme zinciri: Gemini API (varsa) -> Yerel küçük dil modeli
        (indirilmişse) -> her zaman çalışan statik kural motoru. Her katman kendinden
        önceki başarısız olursa devreye girer, hiçbiri kullanıcıyı bekletmeden çöktürmez.
        Teknik hata detayları sadece log dosyasına yazılır (konsolda gürültü yapmaz).
        Başarısızlık durumu süreç genelinde (tüm GeminiAIProvider nesneleri arasında)
        paylaşılır ve süreli bir soğuma sonrası otomatik olarak tekrar denenir.
        """
        if self.is_available():
            try:
                return gemini_fn()
            except Exception as e:
                logger.debug(f"Gemini {label} başarısız oldu ({e}). Yerel model deneniyor.")
                if time.time() >= _provider_state["gemini_down_until"]:
                    print_info("Gemini API şu an yanıt vermiyor, yerel motora geçildi.")
                _provider_state["gemini_down_until"] = time.time() + _DOWN_COOLDOWN_SECONDS

        if local_llm_engine.is_available() and time.time() >= _provider_state["local_llm_down_until"]:
            try:
                return local_fn()
            except Exception as e:
                logger.debug(f"Yerel dil modeli {label} başarısız oldu ({e}). Statik motor devrede.")
                _provider_state["local_llm_down_until"] = time.time() + _DOWN_COOLDOWN_SECONDS

        return fallback_fn()

    def _has_real_ai(self) -> bool:
        """Gemini API veya yerel dil modelinden en az biri gerçekten kullanılabilir mi?"""
        return self.has_real_ai()

    def has_real_ai(self) -> bool:
        """
        Gemini API veya yerel dil modelinden en az biri gerçekten kullanılabilir mi?
        (Public: main.py gibi dış çağıranların settings.gemini_api_key'in salt VAR OLMASI
        yerine gerçek kullanılabilirliği sorgulaması için — istemci kurulumu başarısız
        olduysa veya süreç bu oturumda 'düşmüş' işaretlendiyse burada da yansır.)
        """
        return self.is_available() or (
            local_llm_engine.is_available() and time.time() >= _provider_state["local_llm_down_until"]
        )

    def extract_target_profile(self, raw_text: str) -> TargetProfile:
        """
        Girdiyi analiz eder. API erişilebilir ise Gemini Structured Output kullanır.
        Erişilemez veya hata verirse otomatik olarak Deterministik Fallback motoruna geçer.
        """
        if not raw_text or not raw_text.strip():
            return TargetProfile()

        profile = self._cascade(
            gemini_fn=lambda: self._extract_via_gemini(raw_text),
            local_fn=lambda: self._extract_via_local_llm(raw_text),
            fallback_fn=lambda: self._extract_via_fallback(raw_text),
            label="profil çıkarımı"
        )

        # Kategori tahmini (evcil hayvan/çocuk/lakap ismi) ve ilgi alanı çağrışımı (kahve->latte)
        # sadece gerçek bir AI (Gemini veya yerel model) varken yapılır. Statik sözlükler küçük
        # ve genellenemez olduğu için AI'sız modda alakasız/Türkçe'ye uygun olmayan kelimeler
        # üretebiliyordu; AI yoksa sadece kullanıcının bizzat girdiği kelimeler kullanılır.
        if self._has_real_ai():
            profile = self._enrich_with_unknown_category_guesses(raw_text, profile)
            profile = self._enrich_with_interest_associations(profile)
        return profile

    # Takım/kulüp anahtar kelimeleri: bunlar zaten ranking_engine/candidate_generator'daki
    # özel takım-yılı mantığıyla işleniyor, bu yüzden genel çağrışım genişletmesine dahil edilmez.
    KNOWN_CLUB_KEYWORDS = {
        'besiktas', 'bjk', 'fenerbahce', 'fener', 'fb', 'galatasaray', 'gs',
        'trabzonspor', 'ts', 'bursaspor'
    }

    # İlgi alanı / kişilik özelliği -> somut, parola-uyumlu çağrışım kelimeleri (offline sözlük).
    ASSOCIATION_HEURISTIC_MAP = {
        'kahve': ['Latte', 'Americano', 'Espresso', 'Mocha', 'Cappuccino', 'Filtrekahve', 'Sutlukahve'],
        'cay': ['Demli', 'Acikcay', 'Bergamot'],
        'kitap': ['Roman', 'Kutuphane', 'Sayfa', 'Kurgu'],
        'muzik': ['Melodi', 'Ritim', 'Nota', 'Konser'],
        'sinema': ['Film', 'Senaryo', 'Perde'],
        'film': ['Sinema', 'Senaryo', 'Perde'],
        'yemek': ['Lezzet', 'Tarif', 'Mutfak'],
        'seyahat': ['Gezgin', 'Valiz', 'Rota', 'Pasaport'],
        'oyun': ['Oyuncu', 'Level', 'Skor'],
        'neseli': ['Enerji', 'Pembe', 'Gulen', 'Mutlu', 'Nese'],
        'mutlu': ['Enerji', 'Pembe', 'Gulen', 'Nese'],
        'enerjik': ['Enerji', 'Hiz', 'Dinamik'],
        'sakin': ['Huzur', 'Sessiz', 'Mavi'],
        'huzunlu': ['Melankoli', 'Gri', 'Yagmur'],
        'gitar': ['Akor', 'Melodi', 'Solo'],
    }

    def _enrich_with_interest_associations(self, profile: TargetProfile) -> TargetProfile:
        """
        Profildeki her ilgi alanı/kişilik özelliği için (takım isimleri hariç) somut,
        parolada kullanılabilecek çağrışım kelimeleri üretip keywords'e ekler.
        Örn: 'kahve' -> Latte, Americano, Sutlukahve; 'neseli' -> Enerji, Pembe.
        """
        if not profile.interests:
            return profile

        extra_associations = set(profile.association_words)
        for interest in profile.interests:
            interest_lower = interest.lower()
            if interest_lower in self.KNOWN_CLUB_KEYWORDS:
                continue
            try:
                associations = self.expand_associations(interest, profile)
                if associations:
                    extra_associations.update(a.strip().capitalize() for a in associations if a.strip())
            except Exception as e:
                logger.debug(f"'{interest}' için çağrışım genişletmesi başarısız oldu: {e}")

        profile.association_words = sorted(extra_associations)
        return profile

    def expand_associations(self, term: str, profile: TargetProfile) -> list[str]:
        """
        Bir ilgi alanı/kişilik özelliği kelimesini, onunla anlamsal olarak ilişkili
        somut/özel kelimelere genişletir (örn: 'kahve' -> 'latte', 'americano').
        Gerçek bir AI (Gemini/yerel model) yoksa boş liste döner — statik sözlük tek
        başına alakasız/Türkçe'ye uygun olmayan kelimeler üretebildiği için, bu kural
        çağıran her yerden bağımsız olarak burada da (extract_target_profile'daki
        _has_real_ai() kontrolüne ek olarak) zorlanır.
        """
        if not self._has_real_ai():
            return []
        return self._cascade(
            gemini_fn=lambda: self._expand_associations_via_gemini(term),
            local_fn=lambda: self._expand_associations_via_local_llm(term),
            fallback_fn=lambda: self._expand_associations_heuristic(term),
            label=f"'{term}' çağrışım genişletmesi"
        )

    def _expand_associations_via_local_llm(self, term: str) -> list[str]:
        system = "Sen bir parola tahmin uzmanısın. Sadece istenen JSON liste formatında yanıt ver, başka açıklama ekleme."
        user = (
            f"Örnek girdi: 'kahve' -> Örnek çıktı: [\"latte\", \"americano\", \"espresso\", \"mocha\", \"filtrekahve\"]\n"
            f"Örnek girdi: 'neseli' -> Örnek çıktı: [\"enerji\", \"pembe\", \"mutlu\", \"gulen\", \"nese\"]\n\n"
            f"Şimdi gerçek girdi: '{term}'\n"
            f"Bununla anlamsal olarak ilişkili, YUKARIDAKİ ÖRNEKLERİ KOPYALAMADAN, '{term}' kelimesine özgü "
            f"10 adet SOMUT kelime üret. Sadece JSON dizisi olarak yanıt ver, başka hiçbir şey yazma."
        )
        data = local_llm_engine.generate_json(system, user, max_tokens=250)
        if isinstance(data, list):
            values = [str(x).strip() for x in data if str(x).strip()]
            if values:
                return values
        raise ValueError("Yerel model geçerli bir çağrışım listesi döndürmedi.")

    def _expand_associations_via_gemini(self, term: str) -> list[str]:
        prompt = (
            f"Bir kişinin ilgi alanı veya kişilik özelliği: \"{term}\".\n"
            f"Bu ilgi alanı/özellikle anlamsal olarak İLİŞKİLİ, parolada kullanılabilecek 10-15 adet "
            f"SOMUT ve ÖZEL kelime öner (genel/soyut kelimeler değil).\n"
            f"Örnek: 'kahve' -> latte, americano, espresso, mocha, sutlukahve. "
            f"'neseli' -> enerji, pembe, gulen, mutlu, nese.\n"
            f"Yanıtı SADECE JSON string listesi olarak ver: [\"kelime1\", \"kelime2\", ...]"
        )
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        if hasattr(response, "text") and response.text:
            data = json.loads(response.text)
            if isinstance(data, list):
                values = [str(x).strip() for x in data if str(x).strip()]
                if values:
                    return values
        return self._expand_associations_heuristic(term)

    def _expand_associations_heuristic(self, term: str) -> list[str]:
        term_lower = _normalize_tr(term.lower())
        for key, values in self.ASSOCIATION_HEURISTIC_MAP.items():
            if key in term_lower or term_lower in key:
                return list(values)
        return []

    def _enrich_with_unknown_category_guesses(self, raw_text: str, profile: TargetProfile) -> TargetProfile:
        """
        Metinde "var ama adını/ismini bilmiyorum" gibi bir kategori var-fakat-değeri-yok
        ifadesi tespit edilirse, o kategori için en olası değerleri tahmin edip profile ekler.
        """
        try:
            categories = self._detect_unknown_categories(raw_text)
        except Exception as e:
            logger.debug(f"Bilinmeyen kategori tespiti başarısız oldu ({e}).")
            categories = []

        if not categories:
            return profile

        extra_keywords = set(profile.keywords)
        for category in categories:
            try:
                guesses = self.infer_unknown_values(category, profile)
                extra_keywords.update(g.strip().capitalize() for g in guesses if g.strip())
                logger.info(
                    f"Metinde '{category}' kategorisi belirtilmiş ama değeri verilmemiş; "
                    f"{len(guesses)} olası değer otomatik eklendi."
                )
            except Exception as e:
                logger.debug(f"'{category}' kategorisi için tahmin başarısız oldu: {e}")

        profile.keywords = sorted(extra_keywords)
        return profile

    def _detect_unknown_categories(self, raw_text: str) -> list[str]:
        """Metinde 'var ama değerini bilmiyorum' türünden ifade edilen kategorileri tespit eder."""
        return self._cascade(
            gemini_fn=lambda: self._detect_unknown_categories_via_gemini(raw_text),
            local_fn=lambda: self._detect_unknown_categories_via_local_llm(raw_text),
            fallback_fn=lambda: self._detect_unknown_categories_heuristic(raw_text),
            label="bilinmeyen kategori tespiti"
        )

    def _detect_unknown_categories_via_local_llm(self, raw_text: str) -> list[str]:
        valid_keys = list(self.CATEGORY_LABELS.keys())
        system = "Sen bir metin sınıflandırma asistanısın. Sadece istenen JSON liste formatında yanıt ver."
        user = (
            f"Aşağıdaki metinde, hedef kişi hakkında şu kategorilerden hangilerinin VAR OLDUĞU belirtiliyor "
            f"ama TAM DEĞERİ verilmiyor ya da 'bilmiyorum/hatırlamıyorum' deniyor:\n"
            + "\n".join(f"- {k}: {v}" for k, v in self.CATEGORY_LABELS.items()) + "\n\n"
            f"Sadece ilgili kategori anahtarlarını ({valid_keys}) JSON string listesi olarak ver. "
            f"Hiçbiri yoksa boş liste [] ver.\n\nMetin: \"\"\"{raw_text}\"\"\""
        )
        data = local_llm_engine.generate_json(system, user, max_tokens=100)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip() in valid_keys]
        raise ValueError("Yerel model geçerli bir kategori listesi döndürmedi.")

    def _detect_unknown_categories_via_gemini(self, raw_text: str) -> list[str]:
        valid_keys = list(self.CATEGORY_LABELS.keys())
        prompt = (
            f"Aşağıdaki metinde, hedef kişi hakkında şu kategorilerden hangilerinin VAR OLDUĞU belirtiliyor "
            f"ama TAM DEĞERİ (isim/kelime) verilmiyor ya da açıkça 'bilmiyorum/hatırlamıyorum' deniyor:\n"
            + "\n".join(f"- {k}: {v}" for k, v in self.CATEGORY_LABELS.items()) + "\n\n"
            f"Sadece ilgili kategori anahtarlarını ({valid_keys}) JSON string listesi olarak ver "
            f"(örn: [\"pet\", \"nickname\"]). Hiçbiri yoksa boş liste [] ver.\n\n"
            f"Metin:\n\"\"\"\n{raw_text}\n\"\"\""
        )
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        if hasattr(response, "text") and response.text:
            data = json.loads(response.text)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip() in valid_keys]
        return []

    UNKNOWN_VALUE_CUES = [
        "bilmiyorum", "bilmiyoruz", "hatırlamıyorum", "hatırlamıyoruz", "hatirlamiyorum"
    ]
    CATEGORY_EXISTENCE_CUES = {
        "pet": ["köpeği var", "kedisi var", "köpeğim var", "kedim var", "evcil hayvanı var", "evcil hayvan"],
        "child": ["çocuğu var", "oğlu var", "kızı var", "kardeşi var"],
        "nickname": ["lakabı var", "takma adı var", "bir lakabı"],
        "color": ["sevdiği bir renk", "favori rengi", "en sevdiği renk"],
    }

    def _detect_unknown_categories_heuristic(self, raw_text: str) -> list[str]:
        lower = raw_text.lower()
        if not any(cue in lower for cue in self.UNKNOWN_VALUE_CUES):
            return []
        found = []
        for category, cues in self.CATEGORY_EXISTENCE_CUES.items():
            if any(cue in lower for cue in cues):
                found.append(category)
        return found

    def generate_semantic_password_roots(self, profile: TargetProfile) -> list[str]:
        """
        Hedef profilden anlamsal olarak tutarlı, psikolojik olarak en yüksek olasılıklı kök kalıpları çıkarır.
        """
        return self._cascade(
            gemini_fn=lambda: self._generate_roots_via_gemini(profile),
            local_fn=lambda: self._generate_roots_via_local_llm(profile),
            fallback_fn=lambda: self._generate_roots_via_heuristic(profile),
            label="semantik kök üretimi"
        )

    def _generate_roots_via_local_llm(self, profile: TargetProfile) -> list[str]:
        system = "Sen bir siber güvenlik denetim uzmanısın. Sadece istenen JSON liste formatında yanıt ver."
        user = (
            f"Örnek girdi: isim='Ahmet', tarih='2007', takım='besiktas' -> "
            f"Örnek çıktı: [\"ahmet2007\", \"Ahmet1903\", \"ahmet_bjk\", \"Bjk.Ahmet\", \"ahmet07\"]\n\n"
            f"Şimdi gerçek hedef profili: isimler={profile.names}, tarihler={profile.dates}, "
            f"konumlar={profile.locations}, ilgi alanları={profile.interests}.\n"
            f"YUKARIDAKİ ÖRNEĞİ KOPYALAMADAN, bu GERÇEK profile özgü, bu kişinin parola koyarken kullanacağı "
            f"EN MANTIKLI 20 adet kök kelime/şablon üret (isim+tarih, isim+takım gibi). "
            f"KURAL: Beşiktaşlıysa 1907/1905 ekleme, '1903'/'bjk' ekle; Fenerbahçeliyse '1907'/'fener' ekle; "
            f"Galatasaraylıysa '1905'/'gs' ekle. Sadece JSON dizisi olarak yanıt ver, başka hiçbir şey yazma."
        )
        data = local_llm_engine.generate_json(system, user, max_tokens=900)
        if isinstance(data, list):
            values = [str(x).strip() for x in data if str(x).strip()]
            if values:
                return values
        raise ValueError("Yerel model geçerli bir kök listesi döndürmedi.")

    CATEGORY_LABELS = {
        "pet": "evcil hayvan (köpek/kedi) ismi",
        "child": "çocuk veya küçük kardeş ismi",
        "nickname": "lakap / takma ad",
        "color": "en sevdiği renk",
    }

    # Kategori bilinmiyorsa (AI kapalı) kullanılan, Türkiye bağlamında en yaygın değer listeleri.
    CATEGORY_HEURISTIC_VALUES = {
        "pet": [
            "Boncuk", "Karabas", "Pamuk", "Zeytin", "Duman", "Minnos", "Comar",
            "Fistik", "Bobby", "Luna", "Max", "Seker", "Toprak", "Kaplan", "Pofuduk",
            "Coco", "Findik", "Sisi", "Simba", "Bella"
        ],
        "child": [
            "Ahmet", "Mehmet", "Ali", "Ayse", "Fatma", "Zeynep", "Elif", "Mustafa",
            "Emre", "Ece", "Deniz", "Can", "Cem", "Efe", "Yusuf", "Defne", "Asel", "Miray"
        ],
        "nickname": [
            "Aslan", "Kaplan", "Prenses", "Tatli", "Kucuk", "Canim", "Bebek", "Sahin", "Kartal"
        ],
        "color": [
            "Mavi", "Kirmizi", "Siyah", "Beyaz", "Mor", "Yesil", "Sari", "Pembe", "Turuncu"
        ],
    }

    def infer_unknown_values(self, category: str, profile: TargetProfile) -> list[str]:
        """
        Bilinmeyen bir kategori (ör. isimi bilinmeyen evcil hayvan) için en olası değerleri tahmin eder.
        Gerçek bir AI (Gemini/yerel model) yoksa boş liste döner — bkz. expand_associations
        docstring'indeki aynı gerekçe.
        """
        if not self._has_real_ai():
            return []
        return self._cascade(
            gemini_fn=lambda: self._infer_via_gemini(category, profile),
            local_fn=lambda: self._infer_via_local_llm(category, profile),
            fallback_fn=lambda: self._infer_via_heuristic(category),
            label=f"'{category}' kategori tahmini"
        )

    def _infer_via_local_llm(self, category: str, profile: TargetProfile) -> list[str]:
        label = self.CATEGORY_LABELS.get(category, category)
        system = "Sen bir OSINT ve parola tahmin uzmanısın. Sadece istenen JSON liste formatında yanıt ver."
        user = (
            f"Örnek girdi: kategori='evcil hayvan ismi' -> "
            f"Örnek çıktı: [\"Boncuk\", \"Karabas\", \"Pamuk\", \"Zeytin\", \"Duman\"]\n\n"
            f"Şimdi gerçek kategori: \"{label}\". Hedef kişi hakkında bilinenler: isimler={profile.names}, "
            f"tarihler={profile.dates}, konumlar={profile.locations}, ilgi alanları={profile.interests}.\n"
            f"YUKARIDAKİ ÖRNEĞİ KOPYALAMADAN, Türkiye bağlamında bu GERÇEK kategori ve profile uygun "
            f"EN OLASI 12 değeri tahmin et. Sadece JSON dizisi olarak yanıt ver, başka hiçbir şey yazma."
        )
        data = local_llm_engine.generate_json(system, user, max_tokens=350)
        if isinstance(data, list):
            values = [str(x).strip() for x in data if str(x).strip()]
            if values:
                return values
        raise ValueError("Yerel model geçerli bir tahmin listesi döndürmedi.")

    def _infer_via_gemini(self, category: str, profile: TargetProfile) -> list[str]:
        label = self.CATEGORY_LABELS.get(category, category)
        prompt = (
            f"Sen bir OSINT ve parola tahmin uzmanısın. Hedef kişi hakkında şu bilgiler biliniyor:\n"
            f"- İsimler: {profile.names}\n"
            f"- Tarihler: {profile.dates}\n"
            f"- Konumlar: {profile.locations}\n"
            f"- İlgi Alanları: {profile.interests}\n\n"
            f"Ancak şu kategori için TAM DEĞER bilinmiyor: \"{label}\".\n"
            f"GÖREV: Türkiye bağlamında, bu kişinin profiline uygun EN OLASI 20 adet değeri tahmin et "
            f"(örn. kategori 'evcil hayvan ismi' ise Türkiye'de en yaygın köpek/kedi isimlerini öner).\n"
            f"Yanıtı SADECE JSON formatında bir string listesi olarak ver: [\"deger1\", \"deger2\", ...]"
        )
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        if hasattr(response, "text") and response.text:
            data = json.loads(response.text)
            if isinstance(data, list):
                values = [str(x).strip() for x in data if str(x).strip()]
                if values:
                    return values
        return self._infer_via_heuristic(category)

    def _infer_via_heuristic(self, category: str) -> list[str]:
        return list(self.CATEGORY_HEURISTIC_VALUES.get(category, []))

    def _generate_roots_via_gemini(self, profile: TargetProfile) -> list[str]:
        """Gemini ile hedefin psikolojisine ve takımlarına göre anlamsal kökler üretir."""
        prompt = (
            f"Sen bir siber güvenlik denetim uzmanısın. Aşağıdaki hedef profilini analiz et:\n"
            f"- İsimler: {profile.names}\n"
            f"- Tarihler: {profile.dates}\n"
            f"- Konumlar: {profile.locations}\n"
            f"- İlgi Alanları/Takım: {profile.interests}\n"
            f"- Anahtar Kelimeler: {profile.keywords}\n\n"
            f"GÖREV:\n"
            f"Bu kişinin parola koyarken kullanacağı EN MANTIKLI, ANLAMSAL OLARAK TUTARLI 100 adet kök kelime/şablon listesi üret.\n"
            f"KURALLAR:\n"
            f"1. Beşiktaşlıysa asla '1907' veya '1905' ekleme; '1903', 'bjk', 'kartal' ekle.\n"
            f"2. Fenerbahçeliyse '1907', 'fener', 'fb' ekle; Galatasaraylıysa '1905', 'gs', 'aslan' ekle.\n"
            f"3. Saçma karakter kombinasyonları ('?!' gibi) asla üretme.\n"
            f"4. İsimleri evcil hayvanla, doğum yılıyla, sevdiği renkle mantıklı birleştir (örn: 'ahmet_bjk', 'pamuk2007', 'ahmet1903', 'Bjk.Ahmet').\n"
            f"Yanıtı SADECE JSON formatında bir string listesi olarak ver: [\"kalip1\", \"kalip2\", ...]"
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        if hasattr(response, "text") and response.text:
            data = json.loads(response.text)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
            elif isinstance(data, dict) and "passwords" in data:
                return [str(x).strip() for x in data["passwords"] if str(x).strip()]
        return self._generate_roots_via_heuristic(profile)

    def _generate_roots_via_heuristic(self, profile: TargetProfile) -> list[str]:
        """
        Yapay zeka kapalıyken dahi anlamsal tutarlılığı koruyan (Beşiktaş'a 1907 eklemeyen)
        akıllı sezgisel (heuristic) kök motoru.
        """
        roots = set()

        # Takım semantik haritası (asla çelişkili yıl veya lakap eklenmez!)
        team_affinity = {
            'besiktas': {'bjk', '1903', 'kartal', 'karakartal'},
            'bjk': {'besiktas', '1903', 'kartal'},
            'fenerbahce': {'fb', '1907', 'fener', 'kanarya'},
            'fener': {'fb', '1907', 'fenerbahce'},
            'galatasaray': {'gs', '1905', 'cimbom', 'aslan'},
            'gs': {'galatasaray', '1905', 'aslan'},
            'trabzonspor': {'ts', '1967', 'trabzon', 'firtina'},
            'bursaspor': {'bursa', '1963', 'timsah'}
        }

        # İlgili takımın doğru sembollerini bul
        team_symbols = set()
        for interest in profile.interests:
            intl = interest.lower()
            for team_key, symbols in team_affinity.items():
                if team_key in intl:
                    team_symbols.update(symbols)

        # İsimler ve Takım/İlgi Alanı Anlamsal Hibritleri
        for name in profile.names:
            nl = name.lower()
            nc = name.capitalize()

            # 1. Yalın isimler
            roots.add(nl)
            roots.add(nc)

            # 2. İsim + İlgili Takımın DOĞRU sembolü (örn: ahmet1903, AhmetBjk)
            for ts in team_symbols:
                roots.add(f"{nl}{ts}")
                roots.add(f"{nc}{ts}")
                roots.add(f"{ts}{nl}")
                roots.add(f"{nc}_{ts}")
                roots.add(f"{ts}_{nl}")

            # 3. İsim + İlgili Tarih
            for date in profile.dates:
                roots.add(f"{nl}{date}")
                roots.add(f"{nc}{date}")
                roots.add(f"{nc}_{date}")
                roots.add(f"{nc}.{date}")

            # 4. İsim + Konum/Plaka
            for loc in profile.locations:
                roots.add(f"{nl}{loc.lower()}")
                roots.add(f"{nc}{loc}")
                roots.add(f"{nc}_{loc}")

            # 5. İsim + Özel Renk / Kelime (örn: ahmet_mor, AhmetMavi)
            for kw in profile.keywords:
                roots.add(f"{nl}{kw.lower()}")
                roots.add(f"{nc}{kw.capitalize()}")
                roots.add(f"{nc}_{kw.lower()}")

        # Hayvan veya diğer isimler arası ikili mantıksal hibritler (örn: ahmet_pamuk, pamukahmet2007)
        if len(profile.names) >= 2:
            n1, n2 = profile.names[0], profile.names[1]
            roots.add(f"{n1.capitalize()}{n2.capitalize()}")
            roots.add(f"{n1.lower()}_{n2.lower()}")
            for date in profile.dates:
                roots.add(f"{n1.capitalize()}{n2.capitalize()}{date}")

        return sorted(list(roots))

    def _extract_via_local_llm(self, raw_text: str) -> TargetProfile:
        """Yerel küçük dil modeliyle serbest metinden yapılandırılmış profil çıkarır."""
        system = "Sen bir OSINT analistisin. Sadece istenen JSON formatında yanıt ver, başka açıklama ekleme."
        user = (
            "Örnek girdi: \"Ahmet Fenerbahçeli, 1993 doğumlu, İstanbul'da yaşıyor, köpeğinin adı Pamuk.\"\n"
            "Örnek çıktı: {\"names\": [\"Ahmet\", \"Pamuk\"], \"dates\": [\"1993\"], \"locations\": [\"Istanbul\"], "
            "\"interests\": [\"fenerbahce\"], \"relations\": [], \"keywords\": []}\n\n"
            "YUKARIDAKİ ÖRNEĞİ KOPYALAMADAN, şimdi gerçek metinden bir kişi hakkındaki bilgileri çıkar ve "
            "TAM OLARAK aynı JSON şemasıyla döndür:\n"
            '{"names": [], "dates": [], "locations": [], "interests": [], "relations": [["isim1","isim2"]], "keywords": []}\n'
            "- names: SADECE gerçek özel isimler (kişi, eş, çocuk, evcil hayvan) — genel kelimeleri (örn: 'kahve') isim sayma\n"
            "- dates: 4 haneli yıllar\n"
            "- locations: şehir/plaka\n"
            "- interests: hobi, takım, yiyecek/içecek merakı, kişilik özellikleri (tek kelime/kısa ifade)\n"
            "- keywords: lakap, özel kelimeler\n\n"
            f"Gerçek metin: \"\"\"{raw_text}\"\"\""
        )
        data = local_llm_engine.generate_json(system, user, max_tokens=600)
        if isinstance(data, dict):
            allowed_fields = set(TargetProfile.model_fields.keys())
            clean_data = {k: v for k, v in data.items() if k in allowed_fields}
            return TargetProfile(**clean_data)
        raise ValueError("Yerel model geçerli bir profil JSON'u döndürmedi.")

    def _extract_via_gemini(self, raw_text: str) -> TargetProfile:
        """Gemini Structured Output API ile kesin JSON formatında profil çıkarır."""
        prompt = (
            "Aşağıdaki dağınık metinden bir kişi/kurum hakkındaki bilgileri tespit et ve JSON şemasına göre doldur.\n"
            "- names: Hedef kişi, eşi, çocuğu, evcil hayvanı vb. isimler (Türkçe karakterleri koru).\n"
            "- dates: Önemli yıllar (doğum yılı, evlilik yılı vb. 4 haneli formatta).\n"
            "- locations: Şehir, memleket, ilçe veya plaka kodları (örn: 'Istanbul', '34').\n"
            "- interests: Hobiler, tuttuğu takım, müzik grupları, yiyecek/içecek merakı ve kişilik "
            "özellikleri (örn: 'fenerbahce', 'gitar', 'kahve', 'neseli', 'sakin').\n"
            "- relations: İlişkili isim çiftleri (örn: [['Ali', 'Ayse']]).\n"
            "- keywords: Özel takma adlar, şirket, lakaplar.\n\n"
            f"İncelenecek Metin:\n\"\"\"\n{raw_text}\n\"\"\""
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": TargetProfile,
            },
        )

        if hasattr(response, "text") and response.text:
            data = json.loads(response.text)
            return TargetProfile(**data)
        elif hasattr(response, "parsed") and response.parsed:
            return response.parsed
        else:
            raise ValueError("Gemini geçerli bir yapılandırılmış yanıt döndüremedi.")

    def _extract_via_fallback(self, raw_text: str) -> TargetProfile:
        """
        API olmadığında veya çöktüğünde regex ve sözlük tabanlı çalışan
        çevrimdışı (offline) deterministik kural motoru.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        names = set()
        dates = set()
        locations = set()
        interests = set()
        relations = []
        keywords = set()

        # 1. 4 haneli tarihleri veya gün.ay.yıl tarihlerini yakala (örn: 10.10.2004, 2004)
        date_pattern = re.findall(r'\b(?:\d{1,2}[./-]\d{1,2}[./-])?(19\d\d|20[0-2]\d)\b', raw_text)
        for d in date_pattern:
            dates.add(d)

        # 2. Şehir ve Plaka sözlüğü
        tr_cities = {
            'istanbul': '34', 'ankara': '06', 'izmir': '35', 'bursa': '16',
            'antalya': '07', 'adana': '01', 'trabzon': '61', 'konya': '42',
            'eskisehir': '26', 'kocaeli': '41', 'gaziantep': '27'
        }
        raw_lower = raw_text.lower()
        for city, plate in tr_cities.items():
            if city in raw_lower:
                locations.add(city.capitalize())
                locations.add(plate)

        # 3. Spor takımları ve hobiler
        sports_clubs = ['fenerbahce', 'galatasaray', 'besiktas', 'trabzonspor', 'bursaspor']
        for club in sports_clubs:
            if club in raw_lower or ('fener' in raw_lower and 'fenerbahce' not in raw_lower):
                interests.add(club)

        # 3b. Genel ilgi alanı / kişilik özelliği sözlüğü (association-expansion'a girdi sağlar)
        raw_lower_ascii = _normalize_tr(raw_lower)
        for interest_key in self.ASSOCIATION_HEURISTIC_MAP:
            if interest_key in raw_lower_ascii:
                interests.add(interest_key)

        # 4. Doğal Dil Türkçe Kalıp Çıkarımı (NLP Pattern Matching)
        # Örn: "annesi fatma", "babası mehmet", "eşi sevda", "kızı elif", "oğlu can", "hayvanı pamuk", "köpeği karabaş"
        nlp_patterns = [
            (r'\b(?:annesi|annem|anası)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', names),
            (r'\b(?:babası|babam)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', names),
            (r'\b(?:eşi|karısı|kocası|sevgilisi|yarim)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', names),
            (r'\b(?:oğlu|kızı|çocuğu|kardeşi|abisi|ablası)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', names),
            (r'\b(?:hayvanı|köpeği|kedisi|kuşu)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', names),
            (r'\b([a-zA-ZçğıöşüÇĞİÖŞÜ]+)\s+diye\s+(?:hayvan|kedi|köpek)', names),
            (r'\b(?:rengi|renk)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', keywords),
            (r'\b(?:lakabı|şirketi|mesleği)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ]+)', keywords),
        ]
        for pat, target_set in nlp_patterns:
            matches = re.findall(pat, raw_text, re.IGNORECASE)
            for m in matches:
                clean_m = m.strip(" .,-!?")
                if len(clean_m) >= 2 and clean_m.lower() not in ('var', 'yok', 'bir', 'olan', 'diye'):
                    target_set.add(clean_m.capitalize())

        # 5. Satır bazlı anahtar-değer ve kelime ayrıştırması
        for line in lines:
            if ":" in line or "=" in line or "-" in line:
                parts = re.split(r'[:=-]', line, maxsplit=1)
                key = parts[0].strip().lower()
                val = parts[1].strip() if len(parts) > 1 else ""

                key_norm = key.replace('i̇', 'i').replace('ı', 'i').replace('ş', 's').replace('ğ', 'g')
                if any(k in key_norm for k in ('isim', 'ad', 'hedef', 'es', 'cocuk', 'sevgili', 'kopek', 'kedi', 'anne', 'baba')):
                    for sub_name in re.split(r'[,/&+\s]+|\s+ve\s+', val):
                        clean_sub = sub_name.strip(" .,-!?")
                        if len(clean_sub) >= 2:
                            names.add(clean_sub.capitalize())
                    continue
                elif 'takim' in key_norm:
                    interests.add(val.lower())
                    continue
                elif 'sehir' in key_norm or 'konum' in key_norm:
                    locations.add(val.capitalize())
                    continue

            # Serbest metin içindeki büyük harfli kelimeleri yakala (örn: Ahmet Yılmaz)
            words = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ0-9_]{2,}\b', line)
            for w in words:
                w_lower = w.lower()
                if w_lower not in tr_cities and w_lower not in sports_clubs:
                    # Başta gelen büyük harfli kelimeleri doğrudan isim olarak değerlendir
                    names.add(w.capitalize())

        # İki veya daha fazla isim varsa varsayılan ilişki çifti oluştur
        name_list = sorted(list(names))
        if len(name_list) >= 2:
            relations.append([name_list[0], name_list[1]])

        return TargetProfile(
            names=sorted(list(names)),
            dates=sorted(list(dates)),
            locations=sorted(list(locations)),
            interests=sorted(list(interests)),
            relations=relations,
            keywords=sorted(list(keywords))
        )
