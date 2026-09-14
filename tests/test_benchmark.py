"""
Smart Password Auditor (SPA) - Adım 8 Kıyaslama Modülü (Benchmark) Testleri
Default vs AI Targeted vs Hybrid kıyaslaması ve rapor üretimi.
"""

import json
import pytest
from pathlib import Path
from core.benchmark import BenchmarkSuite
from core.test_engine import LocalHashAuditEngine


class TestBenchmarkSuite:
    """Benchmark modülü testleri."""

    def test_run_single_benchmark_match_and_efficiency(self, tmp_path: Path):
        """Tekil wordlist için benchmark ve verimlilik skoru hesabını doğrula."""
        wordlist_file = tmp_path / "test_list.txt"
        words = ["pass1", "pass2", "target_pwd", "pass4", "pass5"]
        wordlist_file.write_text("\n".join(words), encoding="utf-8")

        target_hash = LocalHashAuditEngine.compute_hash_sha256("target_pwd")
        suite = BenchmarkSuite()
        suite.reports_dir = tmp_path / "reports"
        suite.reports_dir.mkdir(parents=True, exist_ok=True)

        res = suite.run_single_benchmark("TEST_MODE", wordlist_file, target_hash)

        assert res["matched"] is True
        assert res["matched_password"] == "target_pwd"
        assert res["position"] == 3
        assert res["total_candidates"] == 5
        # (1 - 3/5) * 100 = 40.0%
        assert res["efficiency_score"] == 40.0

    def test_run_comparative_benchmark_generates_json_report(self, tmp_path: Path):
        """Üçlü karşılaştırmanın JSON raporu ürettiğini doğrula."""
        def_file = tmp_path / "default.txt"
        def_file.write_text("admin\n123456\npassword\nroot", encoding="utf-8")

        ai_file = tmp_path / "ai_list.txt"
        ai_file.write_text("AliSevda\nAli2021\nAli2021!\nSevdaAli", encoding="utf-8")

        hyb_file = tmp_path / "hyb_list.txt"
        hyb_file.write_text("AliSevda\nAli2021\nadmin\n123456", encoding="utf-8")

        # Hedef parola: "Ali2021"
        target_hash = LocalHashAuditEngine.compute_hash_sha256("Ali2021")

        suite = BenchmarkSuite()
        suite.reports_dir = tmp_path / "reports"
        suite.reports_dir.mkdir(parents=True, exist_ok=True)

        out = suite.run_comparative_benchmark(
            target_hash=target_hash,
            default_path=def_file,
            targeted_path=ai_file,
            hybrid_path=hyb_file,
            target_profile_name="Ali Profil"
        )

        report_path = out["report_path"]
        assert report_path.is_file()

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["target_profile"] == "Ali Profil"
        assert "VARSAYILAN (Default)" in [r["mode"] for r in data["benchmark_results"]]
        assert "AI HEDEFLİ (Targeted)" in [r["mode"] for r in data["benchmark_results"]]
        # Default eşleşmemeli, AI ve Hybrid eşleşmeli
        assert data["benchmark_results"][0]["matched"] is False
        assert data["benchmark_results"][1]["matched"] is True
        assert data["winner_mode"] == "AI HEDEFLİ (Targeted)" or data["winner_mode"] == "HİBRİT (Hybrid)"
