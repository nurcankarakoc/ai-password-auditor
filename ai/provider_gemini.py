"""
Cybzenor - Google Gemini AI Sağlayıcısı
google-genai SDK ile Structured Output (TargetProfile) dönüşümü.
Ortak kademeli yedekleme/anahtar rotasyonu/zenginleştirme mantığı
ai/provider_cloud_base.py'deki CloudAIProviderBase'de yaşar.
"""

import os
import json
import logging
from typing import Optional
from config.settings import settings
from utils.logger import logger
from ai.provider_cloud_base import CloudAIProviderBase
from ai.schemas import TargetProfile

# google-genai SDK'sı, "AFC kullanmayın" gibi kendi iç bilgilendirme uyarılarını
# doğrudan konsola basar; kullanıcıya teknik gürültü olarak yansımaması için susturuyoruz.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)


class GeminiAIProvider(CloudAIProviderBase):
    """Google Gemini modellerini kullanarak OSINT verisini yapılandıran sağlayıcı."""

    PROVIDER_LABEL = "Gemini"

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest") -> None:
        if api_key:
            self._keys: list = [api_key]
        elif settings.gemini_api_keys:
            self._keys = list(settings.gemini_api_keys)
        elif settings.gemini_api_key:
            self._keys = [settings.gemini_api_key]
        elif os.getenv("GEMINI_API_KEY"):
            self._keys = [os.getenv("GEMINI_API_KEY")]
        else:
            self._keys = []

        self._key_index = 0
        super().__init__(api_key=self._keys[0] if self._keys else None)
        self.model_name = model_name
        self._client = None
        self.client_init_error: Optional[str] = None

        if self.api_key:
            self._init_client(self.api_key)

    def _init_client(self, key: str) -> bool:
        """Verilen anahtarla Gemini istemcisini kurar. Başarılıysa True döner."""
        try:
            from google import genai
            # http_options.timeout milisaniye cinsindendir. Timeout olmadan, ağ isteği
            # takılırsa hiçbir istisna fırlatılmaz ve kullanıcı süresiz bekler.
            self._client = genai.Client(
                api_key=key,
                http_options={"timeout": self._HTTP_TIMEOUT_SECONDS * 1000},
            )
            self.api_key = key
            self.client_init_error = None
            return True
        except Exception as e:
            # Bu, tekrar eden bir istek hatası değil — istemci hiç kurulamadı demektir
            # (bozuk anahtar formatı, SDK sorunu vb.). Sessiz kalırsa kullanıcı "Gemini
            # Aktif" sanıp hiç fark etmeden offline motorla çalışmaya devam eder.
            self.client_init_error = str(e)
            logger.warning(f"Google GenAI istemcisi başlatılamadı: {e}")
            return False

    def _extract_via_cloud(self, raw_text: str) -> TargetProfile:
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

    def _generate_roots_via_cloud(self, profile: TargetProfile) -> list[str]:
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

    def _expand_associations_via_cloud(self, term: str) -> list[str]:
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

    def _infer_via_cloud(self, category: str, profile: TargetProfile) -> list[str]:
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

    def _detect_unknown_categories_via_cloud(self, raw_text: str) -> list[str]:
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
