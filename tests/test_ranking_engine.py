"""
Smart Password Auditor (SPA) - Adım 5 Ranking Engine Testleri
Skorlama kriterleri, hedefli wordlist üretimi, hibrit birleştirme ve metadata testleri.
"""

from pathlib import Path
import json
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
