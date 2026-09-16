"""
Cybzenor - Adım 1 Birim ve Entegrasyon Testleri
Konfigürasyon doğrulama, log maskeleme ve CLI işlevsellik testleri.
"""

import logging
import pytest
from pydantic import ValidationError

from config.settings import AppSettings, WordlistConfig, load_settings
from utils.logger import SensitiveDataFilter, setup_logger


class TestConfigValidation:
    """Ayar ve Pydantic model doğrulama testleri."""

    def test_default_settings_load(self):
        """Varsayılan ayarların hatasız yüklendiğini doğrula."""
        settings = load_settings()
        assert settings.app_name == "Cybzenor"
        assert settings.wordlist.min_length == 6
        assert settings.wordlist.max_length == 32
        assert settings.wordlist.max_candidates > 0
        assert settings.safety.max_consecutive_failures == 50

    def test_invalid_password_length_constraint(self):
        """max_length < min_length durumunda hata fırlatıldığını doğrula."""
        with pytest.raises(ValidationError):
            WordlistConfig(min_length=12, max_length=6)

    def test_invalid_log_level_rejected(self):
        """Geçersiz log seviyesinin reddedildiğini doğrula."""
        with pytest.raises(ValidationError):
            AppSettings(log_level="SUPER_DEBUG")

    def test_valid_custom_settings(self):
        """Geçerli özel yapılandırma oluşturulabilmeli."""
        custom = AppSettings(
            log_level="DEBUG",
            wordlist=WordlistConfig(min_length=8, max_length=16, max_candidates=1000)
        )
        assert custom.log_level == "DEBUG"
        assert custom.wordlist.min_length == 8
        assert custom.wordlist.max_length == 16


class TestSensitiveDataMasking:
    """Loglarda hassas bilgilerin maskelenmesi testleri."""

    def test_password_in_text_is_masked(self):
        """Parola içeren mesajların filtrelenip maskelendiğini doğrula."""
        filter_instance = SensitiveDataFilter(mask_enabled=True)

        input_text = "Hedef kullanıcının parolası test edildi: password=SuperSecret123!"
        masked = filter_instance.mask_text(input_text)
        assert "SuperSecret123!" not in masked
        assert "password=***MASKED***" in masked

    def test_api_key_is_masked(self):
        """Google Gemini API anahtarının sansürlendiğini doğrula."""
        filter_instance = SensitiveDataFilter(mask_enabled=True)

        fake_api_key = "AIzaSy" + "A" * 33
        # 1. Metin içinde bağımsız API anahtarı
        input_text_raw = f"API çağrısı yapılıyor: {fake_api_key} kullanıldı"
        masked_raw = filter_instance.mask_text(input_text_raw)
        assert fake_api_key not in masked_raw
        assert "AIzaSy*******************************" in masked_raw

        # 2. Anahtar-değer çifti formatında
        input_text_pair = f"api_key={fake_api_key}"
        masked_pair = filter_instance.mask_text(input_text_pair)
        assert fake_api_key not in masked_pair
        assert "api_key=***MASKED***" in masked_pair

    def test_log_record_filtering(self):
        """Gerçek LogRecord nesnesi üzerindeki filtreleme testi."""
        filter_instance = SensitiveDataFilter(mask_enabled=True)
        record = logging.LogRecord(
            name="Cybzenor",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Kimlik denetimi yapıldı: parola=Gizli1234",
            args=(),
            exc_info=None
        )
        filter_instance.filter(record)
        assert "Gizli1234" not in record.msg
        assert "parola=***MASKED***" in record.msg


class TestPlatformHelper:
    """Platform ve terminal yardımcı araç testleri."""

    def test_banner_execution(self, capsys):
        """Banner yazdırmanın çökmeden çalıştığını doğrula."""
        from utils.platform_helper import print_banner
        print_banner(version="1.0.0-test")
        captured = capsys.readouterr()
        assert "AUDITOR" in captured.out
        assert "1.0.0-test" in captured.out

    def test_color_outputs(self, capsys):
        """Renkli durum fonksiyonlarının çalıştığını doğrula."""
        from utils.platform_helper import print_success, print_error, print_warning
        print_success("Başarılı")
        print_error("Hata")
        print_warning("Uyarı")
        captured = capsys.readouterr()
        assert "Başarılı" in captured.out
        assert "Hata" in captured.out
        assert "Uyarı" in captured.out
