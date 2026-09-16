"""
Cybzenor - Adım 2 Wordlist Manager Testleri
Streaming dosya okuma, uzunluk filtreleme, tekilleştirme ve metadata doğrulama testleri.
"""

import json
from pathlib import Path
import pytest

from core.wordlist_manager import WordlistManager


@pytest.fixture
def temp_manager(tmp_path: Path) -> WordlistManager:
    """Geçici test dizininde çalışan WordlistManager örneği."""
    return WordlistManager(base_dir=tmp_path)


class TestWordlistManagerStreaming:
    """Streaming ve generator işlevsellik testleri."""

    def test_stream_lines_reads_generator(self, tmp_path: Path):
        """Dosyanın RAM dostu generator (yield) olarak okunduğunu doğrula."""
        sample_file = tmp_path / "sample.txt"
        sample_file.write_text("pass1\npass2\n\npass3\n   \n", encoding="utf-8")

        lines = list(WordlistManager.stream_lines(sample_file))
        assert lines == ["pass1", "pass2", "pass3"]

    def test_stream_lines_missing_file_raises_error(self, tmp_path: Path):
        """Var olmayan dosya için FileNotFoundError fırlatıldığını doğrula."""
        non_existent = tmp_path / "non_existent.txt"
        with pytest.raises(FileNotFoundError):
            list(WordlistManager.stream_lines(non_existent))


class TestWordlistFilteringAndDedup:
    """Filtreleme ve tekilleştirme testleri."""

    def test_length_filtering(self):
        """min_length ve max_length sınırlarına uymayanların elendiğini doğrula."""
        candidates = ["123", "12345", "123456", "supersecretpassword", "thisisaverylongpasswordthatexceedslimit1234567890"]
        # Min: 6, Max: 20
        filtered = list(WordlistManager.filter_and_deduplicate(candidates, min_length=6, max_length=20))
        assert "123" not in filtered
        assert "12345" not in filtered
        assert "123456" in filtered
        assert "supersecretpassword" in filtered
        assert "thisisaverylongpasswordthatexceedslimit1234567890" not in filtered

    def test_case_insensitive_deduplication(self):
        """Büyük/küçük harf duyarsız tekilleştirme testi."""
        candidates = ["Admin123", "admin123", "ADMIN123", "UniquePass!"]
        filtered = list(WordlistManager.filter_and_deduplicate(candidates, min_length=4, max_length=30, case_sensitive=False))
        # Yalnızca ilk karşılaşılan Admin123 ve UniquePass! kalmalı
        assert len(filtered) == 2
        assert filtered[0] == "Admin123"
        assert filtered[1] == "UniquePass!"

    def test_case_sensitive_deduplication(self):
        """Büyük/küçük harf duyarlı tekilleştirme testi."""
        candidates = ["Admin123", "admin123", "ADMIN123", "admin123"]
        filtered = list(WordlistManager.filter_and_deduplicate(candidates, min_length=4, max_length=30, case_sensitive=True))
        # Admin123, admin123, ADMIN123 farklı kabul edilmeli, 4. mükerrer elenmeli
        assert len(filtered) == 3
        assert set(filtered) == {"Admin123", "admin123", "ADMIN123"}

    def test_char_rule_filtering(self):
        """Karakter kurallarına göre (digit, alphanumeric, numeric_only, special) filtreleme testi."""
        candidates = ["password", "pass123", "12345678", "Pass!Word", "P@ss1234"]

        # 1. En az 1 rakam
        digits = list(WordlistManager.filter_and_deduplicate(candidates, char_rule="digit"))
        assert "password" not in digits
        assert "Pass!Word" not in digits
        assert "pass123" in digits
        assert "12345678" in digits

        # 2. Alfanümerik (hem harf hem rakam)
        alphanum = list(WordlistManager.filter_and_deduplicate(candidates, char_rule="alphanumeric"))
        assert "12345678" not in alphanum
        assert "password" not in alphanum
        assert "pass123" in alphanum

        # 3. Sadece rakamlar (PIN)
        numeric = list(WordlistManager.filter_and_deduplicate(candidates, char_rule="numeric_only"))
        assert numeric == ["12345678"]

        # 4. En az 1 özel karakter
        special = list(WordlistManager.filter_and_deduplicate(candidates, char_rule="special"))
        assert "Pass!Word" in special
        assert "P@ss1234" in special
        assert "password" not in special



class TestWordlistProcessAndMetadata:
    """Dosya işleme ve metadata oluşturma testleri."""

    def test_process_and_save_creates_metadata(self, temp_manager: WordlistManager, tmp_path: Path):
        """İşleme sonrası dosya ve .metadata.json dosyasının üretildiğini doğrula."""
        source = tmp_path / "raw_wordlist.txt"
        source.write_text("short\n123456\n123456\nAdmin2024!\nadmin2024!\nToolongpasswordoverthelimit1234567890\n", encoding="utf-8")

        output = tmp_path / "clean_wordlist.txt"
        meta = temp_manager.process_and_save(
            source_path=source,
            output_path=output,
            min_length=6,
            max_length=20,
            case_sensitive=False
        )

        assert output.is_file()
        metadata_file = output.with_suffix(output.suffix + ".metadata.json")
        assert metadata_file.is_file()

        # Metadata içeriğini doğrula
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta_data = json.load(f)

        assert meta_data["total_source_lines"] == 6
        assert meta_data["unique_written_lines"] == 2  # 123456 ve Admin2024!
        assert meta_data["filtered_or_duplicate_lines"] == 4
        assert meta_data["filters"]["min_length"] == 6
        assert meta_data["filters"]["max_length"] == 20

    def test_get_wordlist_stats(self, temp_manager: WordlistManager, tmp_path: Path):
        """İstatistik alma fonksiyonunun doğruluğunu test et."""
        sample = tmp_path / "stats_test.txt"
        sample.write_text("alpha\nbeta1234\ngamma567890\n", encoding="utf-8")

        stats = temp_manager.get_wordlist_stats(sample)
        assert stats["total_lines"] == 3
        assert stats["min_length"] == 5  # alpha
        assert stats["max_length"] == 11  # gamma567890
        assert stats["file_size_bytes"] > 0


class TestDefaultWordlistIntegrity:
    """Projedeki gerçek default.txt dosyasının şartnameye uygunluğu."""

    def test_default_txt_exists_and_has_1000_entries(self):
        """wordlists/default.txt dosyasının en az 1000 satır içerdiğini doğrula."""
        from core.wordlist_manager import wordlist_manager
        default_file = wordlist_manager.default_wordlist_path

        assert default_file.is_file(), "wordlists/default.txt dosyası mevcut olmalıdır."
        stats = wordlist_manager.get_wordlist_stats(default_file)
        assert stats["total_lines"] >= 1000, f"En az 1000 parola olmalı, bulunan: {stats['total_lines']}"
