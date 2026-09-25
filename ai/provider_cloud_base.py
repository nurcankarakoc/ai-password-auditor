"""
Cybzenor - Bulut AI Sağlayıcıları için Ortak Taban Sınıf
Gemini, OpenAI ve Anthropic gibi farklı bulut AI servislerinin PAYLAŞTIĞI tüm mantığı
(3 katmanlı yedekleme zinciri, anahtar rotasyonu, devre kesici, zenginleştirme,
yerel LLM/statik motor fallback'leri) barındırır. Alt sınıflar sadece "buluta nasıl
konuşulur" kısmını (5 abstract metot) uygular.
"""

import re
import time
from abc import abstractmethod
from typing import Optional
from utils.logger import logger
from ai.base import BaseAIProvider
from ai.schemas import TargetProfile
from ai.local_llm_engine import local_llm_engine
from utils.turkish_data import TR_CITY_PLAKA, TR_CLUB_SYMBOLS

_TR_ASCII_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _normalize_tr(text: str) -> str:
    """Türkçe karakterleri ASCII karşılıklarına çevirir (sözlük anahtar eşleşmesi için)."""
    return text.translate(_TR_ASCII_MAP)


# Süreç genelinde PAYLAŞILAN devre kesici durumu: main.py ve RankingEngine gibi farklı
# yerler ayrı ayrı provider nesneleri oluşturuyor. Bu bayrak nesne-bazlı olsaydı (instance
# attribute), bir kesinti sırasında her yeni provider nesnesi baştan denemek zorunda kalırdı.
# cloud_down_until sağlayıcı adına göre (Gemini/OpenAI/Anthropic) AYRI tutulur — biri düşünce
# diğerleri de "düşmüş" sayılmasın diye.
_DOWN_COOLDOWN_SECONDS = 60
_provider_state = {"cloud_down_until": {}, "local_llm_down_until": 0.0}


class CloudAIProviderBase(BaseAIProvider):
    """
    Tüm bulut AI sağlayıcılarının ortak davranışı. Alt sınıflar şunları uygulamak zorunda:
    PROVIDER_LABEL (sınıf sabiti), _init_client(key), _extract_via_cloud(raw_text),
    _generate_roots_via_cloud(profile), _expand_associations_via_cloud(term),
    _infer_via_cloud(category, profile), _detect_unknown_categories_via_cloud(raw_text).
    """

    PROVIDER_LABEL: str = "AI"

    def _rotate_to_next_key(self) -> bool:
        """Kota dolduğunda listedeki bir sonraki anahtara geçer. Başka anahtar yoksa False döner."""
        self._key_index += 1
        if self._key_index >= len(self._keys):
            return False
        return self._init_client(self._keys[self._key_index])

    def is_available(self) -> bool:
        """API anahtarı ve istemci geçerli mi (ve şu an süreç genelinde 'düşmüş' değil mi)?"""
        down_until = _provider_state["cloud_down_until"].get(self.PROVIDER_LABEL, 0.0)
        return bool(self._client and self.api_key) and time.time() >= down_until

    @abstractmethod
    def _init_client(self, key: str) -> bool:
        """Verilen anahtarla istemciyi kurar. Başarılıysa True döner."""
        raise NotImplementedError

    # Bu anahtar kelimeleri içeren hatalar geçici kabul edilir (sunucu yoğunluğu, zaman
    # aşımı vb.) ve birkaç kez tekrar denenir; kalıcı hatalarda tekrar denemek zaman
    # kaybıdır, o durumda tek denemede yerel modele geçilir.
    _TRANSIENT_ERROR_HINTS = ("503", "unavailable", "timeout", "deadline", "connection")
    # Bazı SDK'lar (openai.APITimeoutError, anthropic.APITimeoutError, httpx.*Timeout) zaman
    # aşımını mesaj metninde değil İSTİSNA SINIFI adında belirtir; bu yüzden tip adına da bakılır.
    _TRANSIENT_EXCEPTION_TYPE_HINTS = ("timeout", "connectionerror", "connecttimeout", "readtimeout")
    # Kota/rate-limit hataları AYRI ele alınır: birkaç saniye içinde kendiliğinden düzelmezler.
    _QUOTA_ERROR_HINTS = ("resource_exhausted", "quota", "429", "rate_limit", "insufficient_quota")
    _QUOTA_COOLDOWN_SECONDS = 300
    # Bir bulut çağrısının ağ isteği bu kadar saniye içinde yanıt vermezse zaman aşımına
    # uğrar (SDK istemcisi kurulurken uygulanır) — aksi halde ağ takılırsa kullanıcı süresiz
    # bekleyebilir, çünkü hiçbir istisna fırlatılmaz ve tekrar deneme/rotasyon devreye giremez.
    _HTTP_TIMEOUT_SECONDS = 20

    def _cascade(self, cloud_fn, local_fn, fallback_fn, label: str, gemini_retries: int = 3, retry_delay_seconds: float = 2.0):
        """
        Üç katmanlı yedekleme zinciri: Bulut AI (varsa) -> Yerel küçük dil modeli
        (indirilmişse) -> her zaman çalışan statik kural motoru.
        """
        if self.is_available():
            last_exception: Optional[Exception] = None
            is_quota_error = False
            while True:  # her anahtar için bir tur
                is_quota_error = False
                for attempt in range(gemini_retries):
                    try:
                        return cloud_fn()
                    except Exception as e:
                        last_exception = e
                        err_lower = str(e).lower()
                        exc_type_lower = type(e).__name__.lower()
                        is_quota_error = any(hint in err_lower for hint in self._QUOTA_ERROR_HINTS)
                        is_transient = not is_quota_error and (
                            any(hint in err_lower for hint in self._TRANSIENT_ERROR_HINTS)
                            or any(hint in exc_type_lower for hint in self._TRANSIENT_EXCEPTION_TYPE_HINTS)
                        )
                        logger.debug(f"{self.PROVIDER_LABEL} {label} denemesi {attempt + 1}/{gemini_retries} başarısız ({e}).")
                        if is_quota_error or not is_transient or attempt == gemini_retries - 1:
                            break
                        time.sleep(retry_delay_seconds)

                if is_quota_error and self._rotate_to_next_key():
                    from utils.platform_helper import print_info
                    print_info(
                        f"Bu {self.PROVIDER_LABEL} API anahtarının kotası doldu, sıradaki anahtara geçiliyor "
                        f"({self._key_index + 1}/{len(self._keys)})..."
                    )
                    continue
                break

            logger.debug(f"{self.PROVIDER_LABEL} {label} başarısız oldu ({last_exception}). Yerel model deneniyor.")
            if time.time() >= _provider_state["cloud_down_until"].get(self.PROVIDER_LABEL, 0.0):
                from utils.platform_helper import print_info
                if is_quota_error:
                    extra = f" Birden fazla ücretsiz anahtar eklemek için 'apikey' komutunu tekrar kullanabilirsiniz." if len(self._keys) <= 1 else ""
                    print_info(
                        f"Kayıtlı {'tek ' if len(self._keys) <= 1 else 'tüm '}{self.PROVIDER_LABEL} API anahtar{'ının' if len(self._keys) <= 1 else 'larının'} "
                        f"kotası doldu. Yerel motora geçildi. Kota genelde birkaç saat içinde sıfırlanır.{extra}"
                    )
                else:
                    print_info(f"{self.PROVIDER_LABEL} API şu an yanıt vermiyor, yerel motora geçildi.")
            _provider_state["cloud_down_until"][self.PROVIDER_LABEL] = time.time() + (
                self._QUOTA_COOLDOWN_SECONDS if is_quota_error else _DOWN_COOLDOWN_SECONDS
            )

        if local_llm_engine.is_available() and time.time() >= _provider_state["local_llm_down_until"]:
            try:
                return local_fn()
            except Exception as e:
                logger.debug(f"Yerel dil modeli {label} başarısız oldu ({e}). Statik motor devrede.")
                _provider_state["local_llm_down_until"] = time.time() + _DOWN_COOLDOWN_SECONDS

        return fallback_fn()

    def _has_real_ai(self) -> bool:
        """Bu bulut sağlayıcı veya yerel dil modelinden en az biri gerçekten kullanılabilir mi?"""
        return self.has_real_ai()

    def has_real_ai(self) -> bool:
        """
        Public: main.py gibi dış çağıranların anahtarın salt VAR OLMASI yerine gerçek
        kullanılabilirliği sorgulaması için — istemci kurulumu başarısız olduysa burada
        da yansır.

        NOT: yerel model için _provider_state["local_llm_down_until"] (geçici soğuma)
        KASITLI OLARAK burada kontrol EDİLMEZ. Bu bayrak, TEK bir arızi çağrı
        başarısız olduğunda 60sn'liğine "düşmüş" işaretlenir; eğer burada da
        kontrol edilseydi, o 60sn boyunca has_real_ai() False dönerdi ve
        infer_unknown_values/expand_associations gibi metotlar _cascade()'e hiç
        girmeden erkenden boş liste dönerdi — hâlbuki _cascade() zaten bu durumda
        (yerel model soğumadayken) güvenli/deterministik sözlük tabanlı fallback'e
        düşecekti. Sonuç: aynı girdi bazen tahmin üretir bazen üretmezdi (kullanıcı
        raporu: "köpeği var" dediğinde bazen isim önerisi geliyor bazen gelmiyor).
        Burada sadece PAKETİN/MODELİN kurulu olup olmadığına bakılır.
        """
        return self.is_available() or local_llm_engine.is_available()

    def extract_target_profile(self, raw_text: str) -> TargetProfile:
        """
        Girdiyi analiz eder. Bulut sağlayıcı erişilebilir ise onu kullanır.
        Erişilemez veya hata verirse otomatik olarak yerel modele/deterministik
        fallback motoruna geçer.
        """
        if not raw_text or not raw_text.strip():
            return TargetProfile()

        profile = self._cascade(
            cloud_fn=lambda: self._extract_via_cloud(raw_text),
            local_fn=lambda: self._extract_via_local_llm(raw_text),
            fallback_fn=lambda: self._extract_via_fallback(raw_text),
            label="profil çıkarımı"
        )

        # AI (özellikle küçük yerel model), serbest metindeki bağlaç/edat gibi anlamsız
        # kelimeleri (ve, ile, da, bir...) sanki kişiye özel bir bilgiymiş gibi isim/ilgi
        # alanı/anahtar kelime olarak çıkarabiliyor. Bunlar kişiye özel değildir ve parola
        # tahmininde sadece gürültüye yol açar; burada elenir.
        profile.names = self._filter_noise_values(profile.names)
        profile.interests = self._filter_noise_values(profile.interests)
        profile.keywords = self._filter_noise_values(profile.keywords)

        # Kategori tahmini (evcil hayvan/çocuk/lakap ismi) ve ilgi alanı çağrışımı (kahve->latte)
        # sadece gerçek bir AI (bulut veya yerel model) varken yapılır.
        if self._has_real_ai():
            profile = self._enrich_with_unknown_category_guesses(raw_text, profile)
            profile = self._enrich_with_interest_associations(profile)
        return profile

    # Türkçe bağlaç/edat/zamir gibi, tek başına hiçbir kişiye özel anlam taşımayan ve
    # parola tahmininde sadece gürültü üreten kelimeler. AI çıkarımı bunları yanlışlıkla
    # isim/ilgi alanı/anahtar kelime sanabiliyor (örn. "Ahmet VE Mehmet" cümlesinde 've'yi).
    TURKISH_STOPWORDS = {
        've', 'ile', 'da', 'de', 'ki', 'mi', 'mı', 'mu', 'mü', 'bir', 'bu', 'şu', 'o',
        'çok', 'ama', 'fakat', 'ancak', 'veya', 'ya', 'hem', 'ise', 'gibi', 'kadar',
        'sonra', 'önce', 'için', 'diye', 'daha', 'en', 'her', 'hiç', 'yani', 'tüm',
        'bütün', 'değil', 'var', 'yok', 'bile', 'artık', 'nasıl', 'niye', 'neden',
    }

    def _filter_noise_values(self, values: list[str]) -> list[str]:
        """
        İsim/ilgi alanı/anahtar kelime listelerinden Türkçe bağlaç/edat gibi anlamsız
        kelimeleri ve çok kısa (<=2 karakter) değerleri eler.
        """
        cleaned = []
        for v in values:
            v_norm = _normalize_tr(v.strip().lower())
            if len(v_norm) < 3 or v_norm in self.TURKISH_STOPWORDS:
                continue
            cleaned.append(v)
        return cleaned

    @abstractmethod
    def _extract_via_cloud(self, raw_text: str) -> TargetProfile:
        raise NotImplementedError

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
        Gerçek bir AI (bulut/yerel model) yoksa boş liste döner — statik sözlük tek
        başına alakasız/Türkçe'ye uygun olmayan kelimeler üretebildiği için, bu kural
        çağıran her yerden bağımsız olarak burada da zorlanır.
        """
        if not self._has_real_ai():
            return []
        return self._cascade(
            cloud_fn=lambda: self._expand_associations_via_cloud(term),
            local_fn=lambda: self._expand_associations_via_local_llm(term),
            fallback_fn=lambda: self._expand_associations_heuristic(term),
            label=f"'{term}' çağrışım genişletmesi"
        )

    @abstractmethod
    def _expand_associations_via_cloud(self, term: str) -> list[str]:
        raise NotImplementedError

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
        """
        Metinde 'var ama değerini bilmiyorum' türünden ifade edilen kategorileri tespit eder.
        Basit/açık durumlar (örn. 'köpeği var') HER ZAMAN deterministik sezgisel motorla da
        ayrıca kontrol edilip AI sonucuyla BİRLEŞTİRİLİR — küçük yerel modelin örnekleme
        rastgeleliği yüzünden aynı girdide tutarsız sonuç verebilmesine karşı güvenlik ağı
        (aynı cümle farklı çalıştırmalarda AI tarafından bazen yakalanıp bazen kaçırılabiliyor).
        """
        ai_result = self._cascade(
            cloud_fn=lambda: self._detect_unknown_categories_via_cloud(raw_text),
            local_fn=lambda: self._detect_unknown_categories_via_local_llm(raw_text),
            fallback_fn=lambda: [],
            label="bilinmeyen kategori tespiti"
        )
        heuristic_result = self._detect_unknown_categories_heuristic(raw_text)
        return sorted(set(ai_result) | set(heuristic_result))

    @abstractmethod
    def _detect_unknown_categories_via_cloud(self, raw_text: str) -> list[str]:
        raise NotImplementedError

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
        # Olgusal sınıflandırma: metinde ne olduğunu tespit ediyoruz, "yaratıcı" olmamalı.
        data = local_llm_engine.generate_json(system, user, max_tokens=100, temperature=0.1)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip() in valid_keys]
        raise ValueError("Yerel model geçerli bir kategori listesi döndürmedi.")

    CATEGORY_EXISTENCE_CUES = {
        "pet": ["köpeği var", "kedisi var", "köpeğim var", "kedim var", "evcil hayvanı var", "evcil hayvan"],
        "child": ["çocuğu var", "oğlu var", "kızı var", "kardeşi var"],
        "nickname": ["lakabı var", "takma adı var", "bir lakabı"],
        "color": ["sevdiği bir renk", "favori rengi", "en sevdiği renk"],
    }

    def _detect_unknown_categories_heuristic(self, raw_text: str) -> list[str]:
        """
        Tamamen deterministik tespit: bir kategorinin VAR OLDUĞU belirtilmişse (örn.
        'köpeği var') tetiklenir — ayrıca 'bilmiyorum' denmesi ŞART DEĞİLDİR, sadece bir
        varlık ifadesi yeterlidir. Türkçe karakter farklarına (ö/o, ğ/g gibi) duyarsız
        karşılaştırma yapılır ki kullanıcı ASCII yazsa da (örn. 'kopegi var') yakalansın.
        """
        lower = _normalize_tr(raw_text.lower())
        found = []
        for category, cues in self.CATEGORY_EXISTENCE_CUES.items():
            if any(_normalize_tr(cue) in lower for cue in cues):
                found.append(category)
        return found

    def generate_semantic_password_roots(self, profile: TargetProfile) -> list[str]:
        """
        Hedef profilden anlamsal olarak tutarlı, psikolojik olarak en yüksek olasılıklı kök kalıpları çıkarır.
        """
        return self._cascade(
            cloud_fn=lambda: self._generate_roots_via_cloud(profile),
            local_fn=lambda: self._generate_roots_via_local_llm(profile),
            fallback_fn=lambda: self._generate_roots_via_heuristic(profile),
            label="semantik kök üretimi"
        )

    @abstractmethod
    def _generate_roots_via_cloud(self, profile: TargetProfile) -> list[str]:
        raise NotImplementedError

    def _generate_roots_via_local_llm(self, profile: TargetProfile) -> list[str]:
        system = "Sen bir siber güvenlik denetim uzmanısın. Sadece istenen JSON liste formatında yanıt ver."
        # Takım kuralı SADECE profilde gerçekten bir kulüp geçiyorsa prompta eklenir —
        # aksi halde küçük model, örnek kuraldaki takımı (örn. '1903'/'bjk') profilde
        # hiç geçmese bile "papağan gibi" tekrarlayabiliyor (bkz. aşağıdaki deterministik
        # _filter_irrelevant_club_references güvenlik ağı, bu prompt iyileştirmesi de
        # bunun ihtimalini baştan azaltır).
        profile_interests_norm = {_normalize_tr(i.lower()) for i in profile.interests}
        mentioned_club = next((c for c in TR_CLUB_SYMBOLS if c in profile_interests_norm), None)
        if mentioned_club:
            club_rule = (
                f"KURAL: Profildeki takım '{mentioned_club}' ile ilgili SADECE şu sembolleri kullan: "
                f"{sorted(TR_CLUB_SYMBOLS[mentioned_club])}. Başka hiçbir takımın sembolünü/yılını EKLEME."
            )
        else:
            club_rule = "KURAL: Profilde hiçbir takım/kulüp belirtilmemiş — kesinlikle hiçbir takım sembolü/yılı (1903, bjk, 1907, fener, 1905, gs vb.) EKLEME."
        user = (
            f"Örnek girdi: isim='Ahmet', tarih='2007', takım='besiktas' -> "
            f"Örnek çıktı: [\"ahmet2007\", \"Ahmet1903\", \"ahmet_bjk\", \"Bjk.Ahmet\", \"ahmet07\"]\n\n"
            f"Şimdi gerçek hedef profili: isimler={profile.names}, tarihler={profile.dates}, "
            f"konumlar={profile.locations}, ilgi alanları={profile.interests}.\n"
            f"YUKARIDAKİ ÖRNEĞİ KOPYALAMADAN, bu GERÇEK profile özgü, bu kişinin parola koyarken kullanacağı "
            f"EN MANTIKLI 20 adet kök kelime/şablon üret (isim+tarih, isim+takım gibi). "
            f"{club_rule} Sadece JSON dizisi olarak yanıt ver, başka hiçbir şey yazma."
        )
        data = local_llm_engine.generate_json(system, user, max_tokens=900)
        if isinstance(data, list):
            values = [str(x).strip() for x in data if str(x).strip()]
            if values:
                return self._filter_irrelevant_club_references(values, profile)
        raise ValueError("Yerel model geçerli bir kök listesi döndürmedi.")

    def _filter_irrelevant_club_references(self, roots: list[str], profile: TargetProfile) -> list[str]:
        """
        Küçük yerel model, prompttaki takım kuralını (Beşiktaşlıysa 1903/bjk ekle gibi)
        profilde o takım hiç geçmese bile "papağan gibi" köklere sızdırabiliyor. Profilde
        GEÇMEYEN bir takıma ait sembol (1903/bjk/fener/gs gibi) içeren kökler elenir.
        Prompt iyileştirmesi bu ihtimali azaltır ama garanti etmez; bu filtre kesin çözümdür.
        """
        profile_interests_norm = {_normalize_tr(i.lower()) for i in profile.interests}
        mentioned_clubs = {club for club in TR_CLUB_SYMBOLS if club in profile_interests_norm}
        allowed_symbols = {mc for club in mentioned_clubs for mc in TR_CLUB_SYMBOLS[club]}
        all_symbols = {sym for symbols in TR_CLUB_SYMBOLS.values() for sym in symbols}
        forbidden_symbols = all_symbols - allowed_symbols

        filtered = []
        for root in roots:
            root_norm = _normalize_tr(root.lower())
            if any(sym in root_norm for sym in forbidden_symbols):
                continue
            filtered.append(root)
        return filtered

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
        Gerçek bir AI (bulut/yerel model) yoksa boş liste döner — bkz. expand_associations
        docstring'indeki aynı gerekçe.
        """
        if not self._has_real_ai():
            return []
        return self._cascade(
            cloud_fn=lambda: self._infer_via_cloud(category, profile),
            local_fn=lambda: self._infer_via_local_llm(category, profile),
            fallback_fn=lambda: self._infer_via_heuristic(category),
            label=f"'{category}' kategori tahmini"
        )

    @abstractmethod
    def _infer_via_cloud(self, category: str, profile: TargetProfile) -> list[str]:
        raise NotImplementedError

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

    def _infer_via_heuristic(self, category: str) -> list[str]:
        return list(self.CATEGORY_HEURISTIC_VALUES.get(category, []))

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
            "- keywords: lakap, özel kelimeler\n"
            "ÖNEMLİ KURALLAR:\n"
            "- SADECE metinde GERÇEKTEN yazan bilgileri çıkar. Metinde olmayan hiçbir tarih/şehir/isim UYDURMA.\n"
            "- 've', 'ile', 'da', 'de', 'bir', 'bu', 'çok' gibi bağlaç/edat kelimelerini ASLA isim/ilgi alanı/anahtar kelime sayma.\n\n"
            f"Gerçek metin: \"\"\"{raw_text}\"\"\""
        )
        # Olgusal çıkarım: metinde ne yazdığını aktarıyoruz, "yaratıcı" olursa halüsinasyon riski artar.
        data = local_llm_engine.generate_json(system, user, max_tokens=600, temperature=0.1)
        if isinstance(data, dict):
            allowed_fields = set(TargetProfile.model_fields.keys())
            clean_data = {k: v for k, v in data.items() if k in allowed_fields}
            profile = TargetProfile(**clean_data)
            # Küçük yerel model iki türlü hata yapabiliyor: (1) uzun bir kelimenin
            # ("arkadaştır") bir parçasını ("arka") sanki ayrı/anlamlı bir kelimeymiş gibi
            # üretmek, (2) metinde HİÇ geçmeyen tarih/şehir gibi bilgi uydurmak (halüsinasyon).
            # Her alanın metinde gerçekten BAĞIMSIZ bir kelime olarak (kelime sınırıyla)
            # geçtiğini doğrula, geçmeyenleri ele.
            profile.names = self._ground_as_whole_words(profile.names, raw_text)
            profile.dates = self._ground_as_whole_words(profile.dates, raw_text)
            profile.locations = self._ground_as_whole_words(profile.locations, raw_text)
            profile.interests = self._ground_as_whole_words(profile.interests, raw_text)
            profile.keywords = self._ground_as_whole_words(profile.keywords, raw_text)
            return profile
        raise ValueError("Yerel model geçerli bir profil JSON'u döndürmedi.")

    def _ground_as_whole_words(self, values: list[str], raw_text: str) -> list[str]:
        """
        Bir değerin, kaynak metinde başka bir kelimenin parçası değil, BAĞIMSIZ bir kelime
        olarak geçtiğini doğrular (\\b kelime sınırı ile). Örn. metin "arkadaştır" içerse
        bile, "arka" değeri bağımsız bir kelime olarak geçmediği için elenir.
        """
        normalized_text = _normalize_tr(raw_text.lower())
        grounded = []
        for v in values:
            v_norm = _normalize_tr(v.strip().lower())
            if v_norm and re.search(r'\b' + re.escape(v_norm) + r'\b', normalized_text):
                grounded.append(v)
        return grounded

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
        tr_cities = TR_CITY_PLAKA
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
                    if len(val) >= 2:
                        interests.add(val.lower())
                    continue
                elif 'sehir' in key_norm or 'konum' in key_norm:
                    if len(val) >= 2:
                        locations.add(val.capitalize())
                    continue

            # Serbest metin içindeki büyük harfli kelimeleri yakala (örn: Ahmet Yılmaz)
            words = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ0-9_]{2,}\b', line)
            for w in words:
                w_lower = w.lower()
                if w_lower not in tr_cities and w_lower not in sports_clubs:
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
