"""
Smart Password Auditor (SPA) - Adım 7 Güvenlik Denetleyicisi (Safety Controller) Testleri
Rate-limit, Lockout, CAPTCHA ve maksimum ardışık hata denetimleri.
"""

import pytest
from pathlib import Path
from core.safety_controller import (
    SafetyController,
    SafetyTriggerReason,
    SafetyTriggeredException,
    MockAuthService,
    run_safety_monitored_audit
)


class TestSafetyControllerUnit:
    """SafetyController mantıksal birim testleri."""

    def test_rate_limit_429_triggers_exception(self):
        """HTTP 429 yanıtı geldiğinde RATE_LIMIT_EXCEEDED ile durdurulduğunu doğrula."""
        controller = SafetyController(abort_on_rate_limit=True)
        with pytest.raises(SafetyTriggeredException) as exc_info:
            controller.evaluate_response(status_code=429, response_text="Too Many Requests")

        assert exc_info.value.reason == SafetyTriggerReason.RATE_LIMIT_EXCEEDED
        assert controller.is_tripped is True
        assert controller.trip_reason == SafetyTriggerReason.RATE_LIMIT_EXCEEDED

    def test_account_lockout_triggers_exception(self):
        """Hesap kilitleme metni veya 423 kodu geldiğinde durdurulduğunu doğrula."""
        controller = SafetyController()
        with pytest.raises(SafetyTriggeredException) as exc_info:
            controller.evaluate_response(status_code=423, response_text="Account locked due to attempts")

        assert exc_info.value.reason == SafetyTriggerReason.ACCOUNT_LOCKED

    def test_captcha_detection_triggers_exception(self):
        """CAPTCHA tespiti durumunda durdurulduğunu doğrula."""
        controller = SafetyController()
        with pytest.raises(SafetyTriggeredException) as exc_info:
            controller.evaluate_response(status_code=403, response_text="Please solve the reCAPTCHA challenge")

        assert exc_info.value.reason == SafetyTriggerReason.CAPTCHA_DETECTED

    def test_max_consecutive_failures_triggers_exception(self):
        """Maksimum ardışık başarısızlık eşiği aşıldığında durdurulduğunu doğrula."""
        controller = SafetyController(max_consecutive_failures=5)

        for _ in range(4):
            controller.evaluate_response(status_code=401, is_success=False)
            assert controller.is_tripped is False

        with pytest.raises(SafetyTriggeredException) as exc_info:
            controller.evaluate_response(status_code=401, is_success=False)

        assert exc_info.value.reason == SafetyTriggerReason.MAX_CONSECUTIVE_FAILURES_EXCEEDED
        assert controller.consecutive_failures == 5

    def test_success_resets_consecutive_failures(self):
        """Başarılı bir girişin ardışık başarısızlık sayacını sıfırladığını doğrula."""
        controller = SafetyController(max_consecutive_failures=10)
        controller.evaluate_response(status_code=401, is_success=False)
        controller.evaluate_response(status_code=401, is_success=False)
        assert controller.consecutive_failures == 2

        controller.evaluate_response(status_code=200, is_success=True)
        assert controller.consecutive_failures == 0
        assert controller.is_tripped is False


class TestMockAuthAndAuditIntegration:
    """MockAuthService ve denetim akış testi."""

    def test_audit_stops_on_mock_rate_limit(self, tmp_path: Path):
        """Mock servisin rate limit vermesi durumunda denetimin güvenle durdurulduğunu doğrula."""
        wordlist_file = tmp_path / "test_words.txt"
        wordlist_file.write_text("\n".join([f"pass_{i}" for i in range(50)]), encoding="utf-8")

        mock_svc = MockAuthService(target_password="pass_40", rate_limit_after=10, delay_ms=0)
        report = run_safety_monitored_audit(wordlist_file, mock_svc)

        assert "SAFETY_HALTED_RATE_LIMIT_EXCEEDED" in report["status"]
        assert report["attempts_made"] == 11
        assert report["matched_password"] is None

    def test_audit_stops_on_mock_lockout(self, tmp_path: Path):
        """Mock servisin lockout vermesi durumunda denetimin durdurulduğunu doğrula."""
        wordlist_file = tmp_path / "test_words.txt"
        wordlist_file.write_text("\n".join([f"pass_{i}" for i in range(50)]), encoding="utf-8")

        mock_svc = MockAuthService(target_password="pass_40", lockout_after_failures=8, delay_ms=0)
        report = run_safety_monitored_audit(wordlist_file, mock_svc)

        assert "SAFETY_HALTED_ACCOUNT_LOCKED" in report["status"]
        assert report["attempts_made"] <= 10

    def test_audit_finds_password_before_limits(self, tmp_path: Path):
        """Sınırlar aşılmadan önce doğru parolanın bulunduğunu doğrula."""
        wordlist_file = tmp_path / "test_words.txt"
        wordlist_file.write_text("wrong1\nwrong2\nsecret123\nwrong3", encoding="utf-8")

        mock_svc = MockAuthService(target_password="secret123", rate_limit_after=20, delay_ms=0)
        report = run_safety_monitored_audit(wordlist_file, mock_svc)

        assert report["status"] == "MATCH_FOUND"
        assert report["matched_password"] == "secret123"
        assert report["attempts_made"] == 3
