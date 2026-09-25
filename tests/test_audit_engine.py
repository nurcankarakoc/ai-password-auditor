"""
Cybzenor - Adım 6 Local Hash Audit Engine Testleri
SHA-256 hesaplama, eşleşme anında erken sonlandırma, pozisyon ve hız ölçüm testleri.
"""

import hashlib
from pathlib import Path
import pytest

from core.hash_audit_engine import LocalHashAuditEngine, AuditResult


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

        # Bu sabit fixture, kullanıcının GUI'de gördüğü data/synthetic_profiles/ klasörü
        # DIŞINDA (tests/fixtures/) tutulur — aksi halde CLI/GUI'de gerçek bir hedef gibi
        # görünüp kullanıcı tarafından yanlışlıkla silinebiliyordu (bkz. proje geçmişi).
        profile_path = Path(__file__).resolve().parent / "fixtures" / "target_01.json"
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

    def test_save_target_profile_to_disk(self, tmp_path: Path, monkeypatch):
        """save_target_profile_to_disk hedef profilini ve hash'ini diske kaydediyor mu?"""
        from ai.schemas import TargetProfile
        from main import save_target_profile_to_disk

        monkeypatch.setattr("main.BASE_DIR", tmp_path)

        # Kullanıcı girdilerini simüle et: İsim = "Test Hedef", Parola = "Gizli123!"
        inputs = iter(["Test Hedef", "Gizli123!"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        profile = TargetProfile(
            names=["Test", "Hedef"],
            dates=["2024"],
            locations=["Ankara"],
            interests=["kodlama"]
        )

        saved_path = save_target_profile_to_disk(profile)
        assert saved_path is not None
        assert saved_path.is_file()

        import json
        with open(saved_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["target_name"] == "Test Hedef"
        assert saved_data["target_id"] == "target_test_hedef"
        assert saved_data["ground_truth"]["plain_password_hint"] == "Gizli123!"
        assert len(saved_data["ground_truth"]["target_hash"]) == 64

    def test_handle_wordlist_bulk_delete(self, tmp_path: Path, monkeypatch):
        """Üretilen listelerin toplu silme işlemi test edilir."""
        from core.wordlist_manager import wordlist_manager
        from main import handle_default_wordlist_operations

        # Test için geçici generated_dir ayarla
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)
        test_file = gen_dir / "ai_targeted_sample.txt"
        test_file.write_text("Password123\n", encoding="utf-8")
        test_meta = gen_dir / "ai_targeted_sample.txt.metadata.json"
        test_meta.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(wordlist_manager, "generated_dir", gen_dir)
        monkeypatch.setattr("main.clear_screen", lambda: None)
        monkeypatch.setattr("main.pause_prompt", lambda: None)

        # Seçenek 5 (silme), ardından T (tümü), ardından 'e' (onay), ardından 6 (ana menüye dön)
        inputs = iter(["5", "T", "e", "6"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        handle_default_wordlist_operations()

        assert not test_file.exists()
        assert not test_meta.exists()

