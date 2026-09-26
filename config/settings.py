"""
Cybzenor - Ayar Yönetimi Modülü
Pydantic tabanlı tip doğrulaması ve konfigürasyon yükleyici.
"""

from pathlib import Path
import json
import os
import sys
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

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Geçersiz log seviyesi '{v}'. Geçerli olanlar: {valid_levels}")
        return upper_v


def _detect_base_dir() -> Path:
    """
    Proje kök dizinini tespit eder. PyInstaller ile donmuş (frozen) bir .exe olarak
    çalışırken normal `__file__` bir geçici çıkarma klasörünü (sys._MEIPASS) gösterir;
    oraya yazılan hiçbir şey (üretilen wordlist, kayıtlı hedef, log vb.) uygulama
    kapanınca SİLİNİR. Bu yüzden donmuş modda BASE_DIR, .exe dosyasının bulunduğu
    KALICI klasör olarak ayarlanır — kullanıcı verisi hep orada kalır.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# Proje kök dizini tespiti
BASE_DIR: Path = _detect_base_dir()
CONFIG_FILE_PATH: Path = BASE_DIR / "config" / "config.json"


def _ensure_seed_data_when_frozen() -> None:
    """
    Donmuş bir .exe ilk kez (kalıcı klasöründe henüz dosyalar yokken) çalıştırıldığında,
    pakete gömülü varsayılan wordlist/config/yerel-AI-modeli kopyalarını .exe'nin yanındaki
    kalıcı klasöre çıkarır. Yalnızca dosya YOKSA kopyalar — kullanıcının sonradan düzenlediği
    veya sildiği bir dosyanın üzerine asla yazmaz. Herhangi bir hata sessizce yutulur
    (en kötü ihtimalle varsayılan liste/model boş/eksik kalır, uygulama yine de açılır).

    Yerel AI modeli (~1GB .gguf) build_exe.py tarafından gömüldüyse, bu sayede kullanıcı
    hiçbir ek indirme/kurulum adımı yapmadan .exe'yi açar açmaz yapay zeka aktif olur —
    Ayarlar sayfasındaki 'Kur' butonu sadece geliştirici derlemelerinde/güncellemede gerekir.
    """
    if not getattr(sys, "frozen", False):
        return
    bundled_root = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    seed_pairs = [
        (bundled_root / "wordlists" / "default.txt", BASE_DIR / "wordlists" / "default.txt"),
        (bundled_root / "config" / "config.json", BASE_DIR / "config" / "config.json"),
    ]
    for gguf in (bundled_root / "models").glob("*.gguf"):
        seed_pairs.append((gguf, BASE_DIR / "models" / gguf.name))
    for src, dst in seed_pairs:
        try:
            if src.is_file() and not dst.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
        except Exception:
            pass


_ensure_seed_data_when_frozen()


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


# Singleton benzeri global settings nesnesi
settings: AppSettings = load_settings()
