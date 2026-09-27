"""
Cybzenor - Adım 5 Ranking Engine Testleri
Skorlama kriterleri, hedefli wordlist üretimi, hibrit birleştirme ve metadata testleri.
"""

from pathlib import Path
import json
import re
import pytest

from ai.schemas import TargetProfile
from core.ranking_engine import RankingEngine


@pytest.fixture
def target_profile() -> TargetProfile:
    return TargetProfile(
        names=["Ali", "Sevda"],
        dates=["2021", "1990"],
        locations=["Istanbul", "34"],
        interests=["fenerbahce"],
        relations=[["Ali", "Sevda"]],
        keywords=["developer"]
    )


class TestRankingEngineScoring:
    """Skorlama kriterlerinin doğruluğu testleri."""

    def test_priority_1_high_score(self, target_profile: TargetProfile):
        """İsim + Yıl veya ilişki ikililerinin en yüksek skoru (Priority 1: >= 90) aldığını doğrula."""
        engine = RankingEngine(target_profile)
        score_direct = engine.calculate_score("Ali2021")
        score_relation = engine.calculate_score("AliSevda")
        score_relation_date = engine.calculate_score("AliSevda2021!")

        assert score_direct >= 90
        assert score_relation >= 90
        assert score_relation_date >= 95

    def test_priority_2_medium_score(self, target_profile: TargetProfile):
        """İsim + Genel ekler veya İlgi alanı + Tarih kombinasyonlarının orta skor (50-80) aldığını doğrula."""
        engine = RankingEngine(target_profile)
        score_suffix = engine.calculate_score("Ali123")
        score_team_date = engine.calculate_score("fenerbahce2021")

        assert 50 <= score_suffix <= 85
        assert 50 <= score_team_date <= 85

    def test_priority_3_leetspeak_score(self, target_profile: TargetProfile):
        """Sadece Leetspeak mutasyonlarının daha düşük öncelik puanı aldığını doğrula."""
        engine = RankingEngine(target_profile)
        score_leet = engine.calculate_score("@l1")
        assert score_leet <= 40

    def test_relation_plus_date_scores_above_plain_name_plus_date(self, target_profile: TargetProfile):
        """
        İlişki ikilisi + tarih (örn. eşinin ismi + evlilik yılı: "AliSevda2021"), sade
        isim + tarih'ten ("Ali2021") KESİNLİKLE daha yüksek skor almalı. Aksi halde,
        max_candidates limitiyle kesme sırasında (bkz. build_targeted_wordlist) sayıca
        çok daha fazla olan sade isim+tarih varyasyonları, çok daha isabetli olan
        ilişki+tarih adaylarını dosyadan tamamen dışarı itebiliyordu (gerçek regresyon,
        bkz. test_build_targeted_wordlist_does_not_drop_high_value_relation_candidate).
        """
        engine = RankingEngine(target_profile)
        assert engine.calculate_score("AliSevda2021") > engine.calculate_score("Ali2021")


class TestRankingEngineFileGeneration:
    """Hedefli ve hibrit wordlist dosya üretim testleri."""

    def test_build_targeted_wordlist_creates_files(self, target_profile: TargetProfile, tmp_path: Path, monkeypatch):
        """build_targeted_wordlist dosya ve .metadata.json üretiyor mu?"""
        monkeypatch.setattr("core.ranking_engine.BASE_DIR", tmp_path)
        engine = RankingEngine(target_profile)

        output_file, metadata = engine.build_targeted_wordlist(output_filename="test_ai_targeted.txt")
        assert output_file.is_file()
        assert output_file.name == "test_ai_targeted.txt"

        meta_file = output_file.with_suffix(".txt.metadata.json")
        assert meta_file.is_file()

        with open(meta_file, "r", encoding="utf-8") as f:
            meta_json = json.load(f)

        assert meta_json["type"] == "AI_TARGETED"
        assert meta_json["total_candidates"] > 0
        assert "priority_distribution" in meta_json

    def test_build_targeted_wordlist_does_not_drop_high_value_relation_candidate(
        self, tmp_path: Path, monkeypatch
    ):
        """
        Regresyon testi: max_candidates limiti düşükken bile ilişki+tarih gibi yüksek
        değerli bir aday (örn. "AliSevda2021" — eşinin ismi + evlilik yılı) dosyaya
        yazılmalı. Önceden dosya, skora bakılmaksızın SADECE üretim sırasına göre
        kesiliyordu; isim+tarih varyasyonlarının hacmi (çok sayıda tarih/konum/anahtar
        kelime ile kasıtlı olarak burada büyütülmüştür) ilişki ikilisi adaylarını
        limitten önce tamamen dışarı itip dosyadan düşürebiliyordu.
        """
        monkeypatch.setattr("core.ranking_engine.BASE_DIR", tmp_path)
        from config.settings import settings
        monkeypatch.setattr(settings.wordlist, "max_candidates", 40)

        noisy_profile = TargetProfile(
            names=["Ali", "Sevda"],
            dates=["2021"],
            # Tier 1'in "isim + konum/anahtar kelime" hacmini kasıtlı şişirir — tek
            # başına ilişki+tarih ile aynı skoru (95) alan ama çok daha az isabetli
            # onlarca isim+konum kombinasyonu üretir.
            locations=[f"sehir{i}" for i in range(30)],
            interests=["fenerbahce"],
            relations=[["Ali", "Sevda"]],
            keywords=["developer"],
        )
        engine = RankingEngine(noisy_profile)
        output_file, _meta = engine.build_targeted_wordlist(output_filename="test_no_drop.txt")

        with open(output_file, "r", encoding="utf-8") as f:
            raw_lines = [l.strip() for l in f if l.strip()]

        # Ayraç/büyük-küçük harf farklarından bağımsız karşılaştırma için sadece
        # alfanumerik karakterleri korunarak sadeleştirilir (örn. "Ali_Sevda_2021!"
        # -> "alisevda2021").
        canon_lines = {re.sub(r"[^a-z0-9]", "", l.lower()) for l in raw_lines}

        assert any(c in ("alisevda2021", "sevdaali2021") for c in canon_lines), (
            "Yüksek değerli ilişki+tarih adayı (AliSevda2021 / SevdaAli2021), düşük "
            "max_candidates limitinde dosyadan düşürülmemeli."
        )

    def test_build_hybrid_wordlist_combines_and_deduplicates(self, target_profile: TargetProfile, tmp_path: Path, monkeypatch):
        """build_hybrid_wordlist hedefli liste ile varsayılan listeyi tekilleştirerek birleştiriyor mu?"""
        monkeypatch.setattr("core.ranking_engine.BASE_DIR", tmp_path)

        # Sahte default.txt oluştur
        fake_default = tmp_path / "wordlists" / "default.txt"
        fake_default.parent.mkdir(parents=True, exist_ok=True)
        fake_default.write_text("123456\npassword\nadmin123\nAli2021\n", encoding="utf-8")

        engine = RankingEngine(target_profile)
        hybrid_file, meta = engine.build_hybrid_wordlist(
            default_wordlist_path=fake_default,
            output_filename="test_hybrid.txt"
        )

        assert hybrid_file.is_file()
        assert meta["type"] == "HYBRID"
        assert meta["targeted_candidates"] > 0
        assert meta["default_candidates"] > 0

        # İçeriği oku; Ali2021 mükerrer olmamalı
        with open(hybrid_file, "r", encoding="utf-8") as hf:
            lines = [l.strip() for l in hf if l.strip()]

        # Tekil olmalı
        assert len(lines) == len(set(lines))
        assert "Ali2021" in lines or "ali2021" in lines
        assert "123456" in lines
