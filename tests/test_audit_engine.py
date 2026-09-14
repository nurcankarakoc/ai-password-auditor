"""
Smart Password Auditor (SPA) - Adım 6 Local Hash Audit Engine Testleri
SHA-256 hesaplama, eşleşme anında erken sonlandırma, pozisyon ve hız ölçüm testleri.
"""

import hashlib
from pathlib import Path
import pytest

from core.test_engine import LocalHashAuditEngine, AuditResult


@pytest.fixture
def audit_engine() -> LocalHashAuditEngine:
    return LocalHashAuditEngine(hash_type="sha256")


class TestLocalHashAuditEngine:
    """Yerel hash denetim motoru testleri."""

    def test_compute_hash_sha256(self, audit_engine: LocalHashAuditEngine):
        """SHA-256 hesaplama doğruluğunu test et."""
        plain = "Password123!"
        expected = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        assert audit_engine.compute_hash(plain) == expected

    def test_audit_successful_match(self, audit_engine: LocalHashAuditEngine, tmp_path: Path):
        """Wordlist içindeki doğru parolanın bulunup erken sonlandığını test et."""
        wordlist_file = tmp_path / "test_list.txt"
        passwords = ["wrongpass1", "wrongpass2", "CorrectSecret2024!", "should_not_reach_here"]
        wordlist_file.write_text("\n".join(passwords) + "\n", encoding="utf-8")

        target_hash = hashlib.sha256("CorrectSecret2024!".encode("utf-8")).hexdigest()

        result = audit_engine.audit_wordlist_stream(
            target_hash=target_hash,
            wordlist_path=wordlist_file
        )

        assert isinstance(result, AuditResult)
        assert result.matched is True
        assert result.matched_password == "CorrectSecret2024!"
        assert result.position == 3  # 3. sırada bulundu
        assert result.total_tested == 3  # 4. adaya hiç geçilmedi (erken sonlandırma kanıtı)
        assert result.duration_seconds >= 0.0

    def test_audit_no_match(self, audit_engine: LocalHashAuditEngine, tmp_path: Path):
        """Eşleşme bulunamadığında listenin tamamının denendiğini test et."""
        wordlist_file = tmp_path / "no_match_list.txt"
        passwords = ["p1", "p2", "p3"]
        wordlist_file.write_text("\n".join(passwords) + "\n", encoding="utf-8")

        fake_hash = hashlib.sha256("non_existent_pwd".encode("utf-8")).hexdigest()

        result = audit_engine.audit_wordlist_stream(
            target_hash=fake_hash,
            wordlist_path=wordlist_file
        )

        assert result.matched is False
        assert result.matched_password is None
        assert result.position == 0
        assert result.total_tested == 3

    def test_synthetic_target_profile_audit(self, audit_engine: LocalHashAuditEngine, tmp_path: Path):
        """Sentetik profil dosyasındaki hedef hash'in denetlendiğini test et."""
        import json
        from config.settings import BASE_DIR

        profile_path = BASE_DIR / "data" / "synthetic_profiles" / "target_01.json"
        assert profile_path.is_file()

        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        target_hash = data["ground_truth"]["target_hash"]

        # Hedefin parolasını içeren bir wordlist oluştur
        test_wl = tmp_path / "synthetic_test.txt"
        test_wl.write_text("123456\nAli123\nAliSevda2021\nAliSevda\n", encoding="utf-8")

        result = audit_engine.audit_wordlist_stream(
            target_hash=target_hash,
            wordlist_path=test_wl
        )

        assert result.matched is True
        assert result.matched_password == "AliSevda2021"
        assert result.position == 3
