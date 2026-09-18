"""
Cybzenor - Ayar Yönetimi Modülü
Pydantic tabanlı tip doğrulaması ve konfigürasyon yükleyici.
"""

from pathlib import Path
import json
import os
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class WordlistConfig(BaseModel):
    """Wordlist üretim ve filtreleme limitleri."""
    min_length: int = Field(default=6, ge=1, le=128, description="Minimum parola uzunluğu")
    max_length: int = Field(default=32, ge=1, le=256, description="Maksimum parola uzunluğu")
    min_candidates: int = Field(default=3_000, ge=1, le=10_000_000, description="Önerilen minimum aday sayısı (bilgilendirme amaçlı)")
    max_candidates: int = Field(default=10_000, ge=100, le=10_000_000, description="Maksimum aday sayısı limiti (wordlist bu sayıda kesilir)")
    deduplicate: bool = Field(default=True, description="Mükerrer adayları filtrele")
    case_sensitive_dedup: bool = Field(default=True, description="Tekilleştirme büyük/küçük harf duyarlı mı?")

    @field_validator("max_candidates")
    @classmethod
    def validate_candidate_bounds(cls, v: int, info) -> int:
        min_c = info.data.get("min_candidates", 3_000)
        if v < min_c:
            raise ValueError(f"max_candidates ({v}), min_candidates ({min_c}) değerinden küçük olamaz.")
        return v

    @field_validator("max_length")
    @classmethod
    def validate_lengths(cls, v: int, info) -> int:
        min_len = info.data.get("min_length", 6)
        if v < min_len:
            raise ValueError(f"max_length ({v}), min_length ({min_len}) değerinden küçük olamaz.")
        return v


class RulesConfig(BaseModel):
    """Deterministik kural motoru varyasyon ayarları."""
    include_leetspeak: bool = Field(default=True, description="Leetspeak permütasyonlarını dahil et")
    include_dates: bool = Field(default=True, description="Tarih kombinasyonlarını dahil et")
    include_relations: bool = Field(default=True, description="İlişki ve eşleşme kombinasyonlarını dahil et")
    include_common_suffixes: bool = Field(default=True, description="Yaygın son ekleri dahil et")
    common_suffixes: List[str] = Field(
        default_factory=lambda: ["123", "!", "1", "12", "1234", "123!", "34", "06", "35"],
        description="Otomatik eklenecek yaygın son ekler"
    )


class SafetyConfig(BaseModel):
    """Güvenlik denetleyicisi (Safety Controller) eşikleri."""
    max_consecutive_failures: int = Field(default=50, ge=1, le=1000, description="Maksimum ardışık başarısız deneme")
    abort_on_rate_limit: bool = Field(default=True, description="HTTP 429 veya kilitlenmede derhal durdur")
    mock_audit_delay_ms: int = Field(default=10, ge=0, le=5000, description="Test motoru simülasyon gecikmesi (ms)")
    online_request_delay_ms: int = Field(default=250, ge=0, le=60_000, description="Canlı login denetiminde istekler arası bekleme (ms)")
    online_request_timeout_seconds: int = Field(default=10, ge=1, le=120, description="Canlı login denetiminde HTTP istek zaman aşımı (sn)")


class AppSettings(BaseModel):
    """Uygulama ana yapılandırma modeli."""
    app_name: str = Field(default="Cybzenor")
    version: str = Field(default="1.0.0")
    log_level: str = Field(default="INFO", description="Log seviyesi: DEBUG, INFO, WARNING, ERROR")
    mask_sensitive_data: bool = Field(default=True, description="Loglarda hassas verileri maskele")
    wordlist: WordlistConfig = Field(default_factory=WordlistConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API Anahtarı (geriye dönük uyumluluk için: listedeki ilk anahtar)")
    gemini_api_keys: List[str] = Field(
        default_factory=list,
        description="Google Gemini API anahtarları listesi. Bir anahtarın kotası dolduğunda otomatik olarak sıradakine geçilir."
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Geçersiz log seviyesi '{v}'. Geçerli olanlar: {valid_levels}")
        return upper_v


# Proje kök dizini tespiti
BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_FILE_PATH: Path = BASE_DIR / "config" / "config.json"


def _load_dotenv_file(env_path: Path) -> None:
    """
    .env dosyasındaki KEY=VALUE satırlarını, zaten ortamda tanımlı olmayan
    değişkenler için os.environ'a yükler (harici bağımlılık gerektirmeyen minimal yükleyici).
    """
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def load_settings(config_path: Optional[Path] = None) -> AppSettings:
    """
    .env dosyasını, konfigürasyon dosyasını (config.json) ve ortam değişkenlerini yükler.
    Dosya bulunamazsa varsayılan güvenli ayarlarla AppSettings nesnesi üretir.
    """
    _load_dotenv_file(BASE_DIR / ".env")

    target_path = config_path or CONFIG_FILE_PATH
    data = {}

    if target_path.is_file():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            # Yapılandırma bozuksa konsola bilgi verip varsayılanlara düşeriz
            print(f"[UYARI] Konfigürasyon dosyası okunamadı ({e}). Varsayılan ayarlar yükleniyor.")

    # Ortam değişkenlerinden hassas anahtarları çek. GEMINI_API_KEYS (çoğul, virgülle
    # ayrılmış) varsa öncelik onundur; yoksa tekil GEMINI_API_KEY tek elemanlı liste olur.
    env_gemini_keys = os.getenv("GEMINI_API_KEYS")
    env_gemini_key = os.getenv("GEMINI_API_KEY")
    if env_gemini_keys:
        key_list = [k.strip() for k in env_gemini_keys.split(",") if k.strip()]
        if key_list:
            data["gemini_api_keys"] = key_list
            data["gemini_api_key"] = key_list[0]
    elif env_gemini_key:
        data["gemini_api_keys"] = [env_gemini_key]
        data["gemini_api_key"] = env_gemini_key

    env_log_level = os.getenv("SPA_LOG_LEVEL")
    if env_log_level:
        data["log_level"] = env_log_level

    try:
        return AppSettings(**data)
    except Exception as e:
        # Örn: eski bir config.json'da max_candidates < min_candidates gibi artık geçersiz
        # bir kombinasyon olabilir. Programı çökertmek yerine varsayılan ayarlara düşeriz.
        print(f"[UYARI] Konfigürasyon doğrulanamadı ({e}). Varsayılan ayarlar yükleniyor.")
        return AppSettings()


ENV_FILE_PATH: Path = BASE_DIR / ".env"


def save_gemini_api_key(api_key: str, replace: bool = False) -> List[str]:
    """
    Gemini API anahtarını .env dosyasına kalıcı olarak yazar (config.json GİBİ git'e
    eklenen bir dosyaya DEĞİL — .env .gitignore'da tanımlıdır, böylece anahtar asla
    yanlışlıkla commit edilmez) ve çalışan süreçteki global `settings` nesnesini günceller.

    Varsayılan olarak EKLER (replace=False): birden fazla ücretsiz-katman anahtarınız
    varsa, biri kota sınırına ulaştığında GeminiAIProvider otomatik olarak sıradakine
    geçebilsin diye hepsi saklanır. replace=True verilirse mevcut anahtarların yerine
    sadece bu tek anahtar yazılır.
    Döndürülen değer: kayıtlı tüm anahtarların (bu yenisi dahil) listesi.
    """
    existing = list(settings.gemini_api_keys) if not replace else []
    if api_key not in existing:
        existing.append(api_key)

    lines = []
    if ENV_FILE_PATH.is_file():
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            lines = [
                line.rstrip("\n") for line in f
                if not line.strip().startswith("GEMINI_API_KEY=") and not line.strip().startswith("GEMINI_API_KEYS=")
            ]

    lines.append(f"GEMINI_API_KEYS={','.join(existing)}")

    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    os.environ["GEMINI_API_KEYS"] = ",".join(existing)
    os.environ.pop("GEMINI_API_KEY", None)
    settings.gemini_api_keys = existing
    settings.gemini_api_key = existing[0] if existing else None
    return existing


# Singleton benzeri global settings nesnesi
settings: AppSettings = load_settings()
