"""
Cybzenor - Google Gemini AI Sağlayıcısı
google-genai SDK ile Structured Output (TargetProfile) dönüşümü ve kural tabanlı fallback mekanizması.
"""

import os
import re
import json
from typing import Optional
from config.settings import settings
from utils.logger import logger
from ai.base import BaseAIProvider
from ai.schemas import TargetProfile


class GeminiAIProvider(BaseAIProvider):
    """Google Gemini modellerini kullanarak OSINT verisini yapılandıran sağlayıcı."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash") -> None:
        key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        super().__init__(api_key=key)
        self.model_name = model_name
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Google GenAI istemcisi başlatılamadı: {e}")

    def is_available(self) -> bool:
        """API anahtarı ve istemci geçerli mi?"""
        return bool(self._client and self.api_key)

    def extract_target_profile(self, raw_text: str) -> TargetProfile:
        """
        Girdiyi analiz eder. API erişilebilir ise Gemini Structured Output kullanır.
        Erişilemez veya hata verirse otomatik olarak Deterministik Fallback motoruna geçer.
        """
        if not raw_text or not raw_text.strip():
            return TargetProfile()

        if self.is_available():
            try:
                return self._extract_via_gemini(raw_text)
            except Exception as e:
                logger.warning(f"Gemini API çağrısında hata oluştu ({e}). Güvenli Fallback motoru devrede.")
                return self._extract_via_fallback(raw_text)
        else:
            logger.info("Gemini API anahtarı tanımlı değil veya servis kapalı. Kural tabanlı Fallback motoru kullanılıyor.")
            return self._extract_via_fallback(raw_text)

    def generate_semantic_password_roots(self, profile: TargetProfile) -> list[str]:
        """
        Hedef profilden anlamsal olarak tutarlı, psikolojik olarak en yüksek olasılıklı kök kalıpları çıkarır.
        """
        if self.is_available():
            try:
                return self._generate_roots_via_gemini(profile)
            except Exception as e:
                logger.warning(f"Gemini kök üretimi başarısız ({e}). Akıllı yerel motor devrede.")
                return self._generate_roots_via_heuristic(profile)
        else:
            return self._generate_roots_via_heuristic(profile)

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

    def _extract_via_gemini(self, raw_text: str) -> TargetProfile:
        """Gemini Structured Output API ile kesin JSON formatında profil çıkarır."""
        prompt = (
            "Aşağıdaki dağınık metinden bir kişi/kurum hakkındaki bilgileri tespit et ve JSON şemasına göre doldur.\n"
            "- names: Hedef kişi, eşi, çocuğu, evcil hayvanı vb. isimler (Türkçe karakterleri koru).\n"
            "- dates: Önemli yıllar (doğum yılı, evlilik yılı vb. 4 haneli formatta).\n"
            "- locations: Şehir, memleket, ilçe veya plaka kodları (örn: 'Istanbul', '34').\n"
            "- interests: Hobiler, tuttuğu takım, müzik grupları vb. (örn: 'fenerbahce', 'gitar').\n"
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
