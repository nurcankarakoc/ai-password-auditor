"""
Smart Password Auditor (SPA) - Ayar Yönetimi Modülü
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
    max_candidates: int = Field(default=500_000, ge=100, le=10_000_000, description="Maksimum aday sayısı limiti")
    deduplicate: bool = Field(default=True, description="Mükerrer adayları filtrele")
    case_sensitive_dedup: bool = Field(default=False, description="Tekilleştirme büyük/küçük harf duyarlı mı?")

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


class AppSettings(BaseModel):
    """Uygulama ana yapılandırma modeli."""
    app_name: str = Field(default="Smart Password Auditor")
    version: str = Field(default="1.0.0")
    log_level: str = Field(default="INFO", description="Log seviyesi: DEBUG, INFO, WARNING, ERROR")
    mask_sensitive_data: bool = Field(default=True, description="Loglarda hassas verileri maskele")
    wordlist: WordlistConfig = Field(default_factory=WordlistConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API Anahtarı (.env veya ortamdan)")

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


def load_settings(config_path: Optional[Path] = None) -> AppSettings:
    """
    Konfigürasyon dosyasını (config.json) ve ortam değişkenlerini yükler.
    Dosya bulunamazsa varsayılan güvenli ayarlarla AppSettings nesnesi üretir.
    """
    target_path = config_path or CONFIG_FILE_PATH
    data = {}

    if target_path.is_file():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            # Yapılandırma bozuksa konsola bilgi verip varsayılanlara düşeriz
            print(f"[UYARI] Konfigürasyon dosyası okunamadı ({e}). Varsayılan ayarlar yükleniyor.")

    # Ortam değişkenlerinden hassas anahtarları çek
    env_gemini_key = os.getenv("GEMINI_API_KEY")
    if env_gemini_key:
        data["gemini_api_key"] = env_gemini_key

    env_log_level = os.getenv("SPA_LOG_LEVEL")
    if env_log_level:
        data["log_level"] = env_log_level

    return AppSettings(**data)


# Singleton benzeri global settings nesnesi
settings: AppSettings = load_settings()
