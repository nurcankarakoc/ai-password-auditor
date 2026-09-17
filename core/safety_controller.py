"""
Cybzenor - Güvenlik Denetleyicisi (Safety Controller)
Etik güvenlik sınırlarını koruyan, anormal yanıtları, HTTP 429 (Rate Limit),
hesap kilitleme (Account Lockout) veya CAPTCHA durumlarını algılayıp
denetimi derhal ve güvenli biçimde durduran mekanizma.
"""

import time
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from config.settings import settings
from utils.logger import logger
from core.wordlist_manager import wordlist_manager


class SafetyTriggerReason(str, Enum):
    """Güvenlik denetleyicisini tetikleyen durum türleri."""
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    MAX_CONSECUTIVE_FAILURES_EXCEEDED = "MAX_CONSECUTIVE_FAILURES_EXCEEDED"
    ANOMALOUS_RESPONSE = "ANOMALOUS_RESPONSE"
    MANUAL_ABORT = "MANUAL_ABORT"


class SafetyTriggeredException(Exception):
    """
    Güvenlik sınırları aşıldığında fırlatılan özel istisna sınıfı.
    Denetimin etik sınırları korumak adına durdurulduğunu bildirir.
    """
    def __init__(self, reason: SafetyTriggerReason, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return f"[SAFETY TRIGGERED: {self.reason.value}] {self.message} | Detaylar: {self.details}"


class SafetyController:
    """
    Denetim trafiğini ve hedef sistemin yanıtlarını gerçek zamanlı izleyen kontrolör.
    """

    LOCKOUT_KEYWORDS = [
        "account locked", "hesap kilitlendi", "too many attempts",
        "temporarily blocked", "gecici olarak engellendi",
        "user is disabled", "kullanici devre disi", "try again later"
    ]

    CAPTCHA_KEYWORDS = [
        "captcha", "recaptcha", "hcaptcha", "robot",
        "guvenlik kodu", "challenge required"
    ]

    def __init__(
        self,
        max_consecutive_failures: Optional[int] = None,
        abort_on_rate_limit: Optional[bool] = None
    ) -> None:
        self.max_consecutive_failures = (
            max_consecutive_failures if max_consecutive_failures is not None
            else settings.safety.max_consecutive_failures
        )
        self.abort_on_rate_limit = (
            abort_on_rate_limit if abort_on_rate_limit is not None
            else settings.safety.abort_on_rate_limit
        )

        self.total_attempts: int = 0
        self.consecutive_failures: int = 0
        self.is_tripped: bool = False
        self.trip_reason: Optional[SafetyTriggerReason] = None
        self.trip_details: Optional[Dict[str, Any]] = None

    def reset(self) -> None:
        """Denetleyici sayaçlarını sıfırlar."""
        self.total_attempts = 0
        self.consecutive_failures = 0
        self.is_tripped = False
        self.trip_reason = None
        self.trip_details = None

    def evaluate_response(
        self,
        status_code: int,
        response_text: str = "",
        is_success: bool = False
    ) -> None:
        """
        Her deneme sonrasında hedef sistemden dönen yanıtı inceler.
        Tehlikeli veya engelleme sinyali varsa SafetyTriggeredException fırlatır.
        """
        self.total_attempts += 1
        resp_lower = response_text.lower()

        # 1. HTTP 429 - Too Many Requests (Rate Limit)
        if status_code == 429:
            if self.abort_on_rate_limit:
                self._trip(
                    reason=SafetyTriggerReason.RATE_LIMIT_EXCEEDED,
                    message="Hedef sistem HTTP 429 (Too Many Requests) döndürdü. Rate-limit aşıldığı için test durduruldu.",
                    details={"status_code": 429, "attempt": self.total_attempts}
                )

        # 2. HTTP 423 (Locked) veya Yanıt Metninde Hesap Kilitleme Tespiti
        if status_code == 423 or any(kw in resp_lower for kw in self.LOCKOUT_KEYWORDS):
            self._trip(
                reason=SafetyTriggerReason.ACCOUNT_LOCKED,
                message="Hedef hesap kilitlendi veya koruma altına alındı (Lockout detected).",
                details={"status_code": status_code, "attempt": self.total_attempts, "response_sample": response_text[:120]}
            )

        # 3. CAPTCHA veya Bot Koruması Tespiti
        if any(kw in resp_lower for kw in self.CAPTCHA_KEYWORDS):
            self._trip(
                reason=SafetyTriggerReason.CAPTCHA_DETECTED,
                message="Sistemde CAPTCHA / Bot doğrulama mekanizması tetiklendi. Otomatik test sonlandırıldı.",
                details={"status_code": status_code, "attempt": self.total_attempts, "response_sample": response_text[:120]}
            )

        # 4. Başarı / Başarısızlık Sayacı Değerlendirmesi
        if is_success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_consecutive_failures:
                self._trip(
                    reason=SafetyTriggerReason.MAX_CONSECUTIVE_FAILURES_EXCEEDED,
                    message=f"Maksimum ardışık başarısızlık eşiği ({self.max_consecutive_failures}) aşıldı. Brute-force koruması devreye girdi.",
                    details={"consecutive_failures": self.consecutive_failures, "total_attempts": self.total_attempts}
                )

    def _trip(self, reason: SafetyTriggerReason, message: str, details: Dict[str, Any]) -> None:
        """Güvenlik mekanizmasını tetikler ve loglar."""
        self.is_tripped = True
        self.trip_reason = reason
        self.trip_details = details

        logger.warning(f"Güvenlik Sınırı Tetiklendi -> Neden: {reason.value} | {message}")
        raise SafetyTriggeredException(reason=reason, message=message, details=details)

    def get_status(self) -> Dict[str, Any]:
        """Kontrolör durum özetini döndürür."""
        return {
            "total_attempts": self.total_attempts,
            "consecutive_failures": self.consecutive_failures,
            "is_tripped": self.is_tripped,
            "trip_reason": self.trip_reason.value if self.trip_reason else None,
            "trip_details": self.trip_details
        }


class MockAuthService:
    """
    Yerel ve güvenli testler için kimlik doğrulama simülatörü.
    Gerçek hedeflere saldırmadan rate-limit, lockout ve başarı durumlarını test etmeyi sağlar.
    """

    def __init__(
        self,
        target_password: str = "Pamuk2021!",
        rate_limit_after: Optional[int] = None,
        lockout_after_failures: Optional[int] = None,
        captcha_after: Optional[int] = None,
        delay_ms: Optional[int] = None
    ) -> None:
        self.target_password = target_password
        self.rate_limit_after = rate_limit_after
        self.lockout_after_failures = lockout_after_failures
        self.captcha_after = captcha_after
        self.delay_ms = delay_ms if delay_ms is not None else settings.safety.mock_audit_delay_ms

        self.call_count: int = 0
        self.failure_count: int = 0

    def attempt_login(self, password: str) -> Tuple[int, str, bool]:
        """
        Bir parola denemesini simüle eder ve (status_code, response_text, is_success) döndürür.
        """
        self.call_count += 1

        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)

        # 1. Rate limit simülasyonu
        if self.rate_limit_after and self.call_count > self.rate_limit_after:
            return 429, "Too Many Requests - Rate limit exceeded. Try again in 60s.", False

        # 2. Lockout simülasyonu
        if self.lockout_after_failures and self.failure_count >= self.lockout_after_failures:
            return 423, "Account locked due to excessive failed login attempts.", False

        # 3. CAPTCHA simülasyonu
        if self.captcha_after and self.call_count > self.captcha_after:
            return 403, "Suspicious activity detected. Please complete the CAPTCHA to continue.", False

        # 4. Doğru parola kontrolü
        if password == self.target_password:
            return 200, "Authentication successful.", True

        # 5. Normal hatalı giriş
        self.failure_count += 1
        return 401, "Invalid credentials.", False


def run_safety_monitored_audit(
    wordlist_path: Path,
    mock_service: MockAuthService,
    safety_controller: Optional[SafetyController] = None,
    exclude_passwords: Optional[set] = None
) -> Dict[str, Any]:
    """
    Wordlist'teki adayları MockAuthService üzerinde SafetyController denetiminde koşturur.
    exclude_passwords verilirse, o kümedeki adaylar (case-insensitive) denenmeden atlanır;
    bilinen/artık geçerli olmayan bir parolanın yanlış pozitif üretmesini engellemek için kullanılır.
    """
    if not wordlist_path.is_file():
        raise FileNotFoundError(f"Wordlist dosyası bulunamadı: {wordlist_path}")

    ctrl = safety_controller or SafetyController()
    ctrl.reset()
    exclude_lower = {p.lower() for p in exclude_passwords} if exclude_passwords else set()

    start_time = time.time()
    matched_password: Optional[str] = None
    stop_reason: str = "COMPLETED_WITHOUT_MATCH"
    error_message: Optional[str] = None

    try:
        for candidate in wordlist_manager.stream_lines(wordlist_path):
            if candidate.lower() in exclude_lower:
                continue
            status_code, resp_text, is_success = mock_service.attempt_login(candidate)

            if is_success:
                matched_password = candidate
                stop_reason = "MATCH_FOUND"
                ctrl.evaluate_response(status_code, resp_text, is_success=True)
                break

            # Yanıtı denetleyiciye ilet (İhlal varsa SafetyTriggeredException fırlatır)
            ctrl.evaluate_response(status_code, resp_text, is_success=False)

    except SafetyTriggeredException as e:
        stop_reason = f"SAFETY_HALTED_{e.reason.value}"
        error_message = e.message
        logger.info(f"Denetim güvenlik kontrolörü tarafından durduruldu: {e.message}")

    elapsed = round(time.time() - start_time, 4)

    return {
        "status": stop_reason,
        "matched_password": matched_password,
        "attempts_made": ctrl.total_attempts,
        "consecutive_failures": ctrl.consecutive_failures,
        "elapsed_seconds": elapsed,
        "error_message": error_message,
        "safety_status": ctrl.get_status()
    }
