"""
Smart Password Auditor (SPA) - Güvenli Loglama Modülü
Hassas verileri (parola, API key, token vb.) otomatik maskeleyen ve
çift kanallı (Konsol + Dosya) loglama sağlayan mekanizma.
"""

import logging
import re
from pathlib import Path
from typing import Optional
from config.settings import settings, BASE_DIR

# Maskelenecek hassas alan regex şablonları
SENSITIVE_PATTERNS = [
    # parola / password / secret / token / key / api_key eşleşmeleri
    re.compile(r'(?i)(password|parola|secret|token|api[_-]?key|gemini[_-]?api[_-]?key)\s*[:=]\s*["\']?([^"\'\s,]+)["\']?'),
    # Google Gemini API key formatı (AIzaSy...)
    re.compile(r'AIzaSy[A-Za-z0-9_-]{33}'),
]


class SensitiveDataFilter(logging.Filter):
    """
    Log kayıtlarındaki hassas bilgileri tespit edip maskeleyen özel filtre.
    """

    def __init__(self, mask_enabled: bool = True) -> None:
        super().__init__()
        self.mask_enabled = mask_enabled

    def mask_text(self, text: str) -> str:
        """Metin içerisindeki gizli verileri sansürler."""
        if not self.mask_enabled:
            return text

        masked_text = text
        # Anahtar-değer çiftlerini maskele (örn: password=123456 -> password=***MASKED***)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.pattern.startswith("AIzaSy"):
                masked_text = pattern.sub("AIzaSy*******************************", masked_text)
            else:
                masked_text = pattern.sub(r'\1=***MASKED***', masked_text)

        return masked_text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.mask_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.mask_text(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.mask_text(str(arg)) if isinstance(arg, str) else arg for arg in record.args)
        return True


def setup_logger(name: str = "SPA", log_file: Optional[Path] = None) -> logging.Logger:
    """
    Uygulama için yapılandırılmış Logger nesnesi döndürür.
    """
    logger = logging.getLogger(name)

    # Zaten handler'lar eklendiyse mükerrer handler eklemeyi önle
    if logger.handlers:
        return logger

    # Log seviyesini ayarla
    numeric_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Maskeleme filtresi
    mask_filter = SensitiveDataFilter(mask_enabled=settings.mask_sensitive_data)
    logger.addFilter(mask_filter)

    # Formatlayıcılar
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )

    # 1. Konsol Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. Dosya Handler (logs/spa.log)
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target_file = log_file or (logs_dir / "spa.log")

    try:
        file_handler = logging.FileHandler(target_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[UYARI] Log dosyası oluşturulamadı: {e}")

    return logger


# Global logger örneği
logger: logging.Logger = setup_logger()
