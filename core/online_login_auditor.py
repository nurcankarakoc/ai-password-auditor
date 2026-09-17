"""
Cybzenor - Canlı Login Denetim Motoru (Online Login Audit Engine)
Gerçek bir HTTP login formuna karşı, SafetyController gözetiminde parola denemesi yapar.
Sadece yetkili (authorized) pentest/denetim hedeflerinde kullanılmalıdır.
"""

import re
import time
from typing import Optional, Tuple, Dict, Any, List

import requests

from config.settings import settings
from utils.logger import logger


class HttpLoginAuditService:
    """
    Gerçek bir HTTP login endpoint'ine karşı parola denemesi yapan servis.
    MockAuthService ile aynı arayüzü (attempt_login -> (status_code, response_text, is_success))
    sağlar, bu sayede core.safety_controller.run_safety_monitored_audit ile doğrudan uyumludur.
    """

    def __init__(
        self,
        target_url: str,
        username_field: str,
        username_value: str,
        password_field: str,
        method: str = "POST",
        content_type: str = "form",
        success_indicator: Optional[str] = None,
        failure_indicator: Optional[str] = None,
        success_status_codes: Optional[List[int]] = None,
        extra_fields: Optional[Dict[str, str]] = None,
        csrf_field: Optional[str] = None,
        csrf_regex: Optional[str] = None,
        csrf_fetch_url: Optional[str] = None,
        request_delay_ms: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        verify_ssl: bool = True,
    ) -> None:
        self.target_url = target_url
        self.username_field = username_field
        self.username_value = username_value
        self.password_field = password_field
        self.method = method.upper()
        self.content_type = content_type
        self.success_indicator = success_indicator
        self.failure_indicator = failure_indicator
        self.success_status_codes = success_status_codes or [200, 301, 302, 303]
        self.extra_fields = extra_fields or {}
        self.csrf_field = csrf_field
        self.csrf_regex = csrf_regex
        self.csrf_fetch_url = csrf_fetch_url or target_url
        self.request_delay_ms = (
            request_delay_ms if request_delay_ms is not None else settings.safety.online_request_delay_ms
        )
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.safety.online_request_timeout_seconds
        )
        self.verify_ssl = verify_ssl

        self.session = requests.Session()
        self.call_count: int = 0

    def _fetch_csrf_token(self) -> Optional[str]:
        if not (self.csrf_field and self.csrf_regex):
            return None
        try:
            resp = self.session.get(self.csrf_fetch_url, timeout=self.timeout_seconds, verify=self.verify_ssl)
            match = re.search(self.csrf_regex, resp.text)
            return match.group(1) if match else None
        except requests.RequestException as e:
            logger.warning(f"CSRF token alınamadı: {e}")
            return None

    def _evaluate_success(self, status_code: int, response_text: str) -> bool:
        if self.success_indicator:
            return self.success_indicator.lower() in response_text.lower()
        if self.failure_indicator:
            return self.failure_indicator.lower() not in response_text.lower()
        return status_code in self.success_status_codes

    def attempt_login(self, password: str) -> Tuple[int, str, bool]:
        """
        Bir parola denemesi yapar ve (status_code, response_text, is_success) döndürür.
        Ağ hatalarında status_code=0 ile başarısız olarak döner (denetim durmaz, sıradaki adaya geçilir).
        """
        self.call_count += 1

        if self.request_delay_ms > 0:
            time.sleep(self.request_delay_ms / 1000.0)

        payload: Dict[str, Any] = {
            self.username_field: self.username_value,
            self.password_field: password,
            **self.extra_fields,
        }

        if self.csrf_field:
            token = self._fetch_csrf_token()
            if token:
                payload[self.csrf_field] = token

        try:
            if self.method == "GET":
                resp = self.session.get(
                    self.target_url, params=payload, timeout=self.timeout_seconds,
                    verify=self.verify_ssl, allow_redirects=False
                )
            elif self.content_type == "json":
                resp = self.session.post(
                    self.target_url, json=payload, timeout=self.timeout_seconds,
                    verify=self.verify_ssl, allow_redirects=False
                )
            else:
                resp = self.session.post(
                    self.target_url, data=payload, timeout=self.timeout_seconds,
                    verify=self.verify_ssl, allow_redirects=False
                )
        except requests.RequestException as e:
            logger.warning(f"Canlı login denemesi başarısız (ağ hatası): {e}")
            return 0, f"NETWORK_ERROR: {e}", False

        status_code = resp.status_code
        response_text = resp.text or ""
        is_success = self._evaluate_success(status_code, response_text)
        return status_code, response_text, is_success
