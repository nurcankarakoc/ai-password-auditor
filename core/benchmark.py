"""
Smart Password Auditor (SPA) - Kıyaslama ve Başarı Analiz Modülü (Benchmark)
Farklı wordlist türlerini (Varsayılan, AI Hedefli, Hibrit) aynı hedef hash üzerinde
yarıştırarak hız, bulunan sıra, süre ve verimlilik skorunu bilimsel olarak ölçer.
"""

import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from core.test_engine import LocalHashAuditEngine
from core.wordlist_manager import wordlist_manager
from config.settings import BASE_DIR
from utils.logger import logger


class BenchmarkSuite:
    """
    Üç farklı wordlist modunun (Default vs AI Targeted vs Hybrid)
    performans ve verimliliğini kıyaslayan modül.
    """

    def __init__(self) -> None:
        self.reports_dir = BASE_DIR / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.engine = LocalHashAuditEngine()

    def run_single_benchmark(
        self,
        mode_name: str,
        wordlist_path: Path,
        target_hash: str,
        expected_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tek bir wordlist için hız, sıra ve verimlilik analizini koşturur."""
        if not wordlist_path.is_file():
            return {
                "mode": mode_name,
                "file": str(wordlist_path.name),
                "status": "FILE_NOT_FOUND",
                "matched": False,
                "matched_password": None,
                "position": None,
                "total_candidates": 0,
                "duration_seconds": 0.0,
                "hashes_per_second": 0.0,
                "efficiency_score": 0.0
            }

        # Toplam satır sayısını al
        stats = wordlist_manager.get_wordlist_stats(wordlist_path)
        total_lines = stats["total_lines"]

        # Audit koştur
        audit_result = self.engine.audit_wordlist_stream(
            target_hash=target_hash,
            wordlist_path=wordlist_path
        )

        matched = audit_result.matched
        position = audit_result.position
        duration = audit_result.duration_seconds
        rate = audit_result.hashes_per_second

        # Verimlilik Skoru (Efficiency Score):
        # Eğer parola erkenden (örn. ilk %1'lik dilimde) bulunduysa verimlilik ~%99'dur.
        # Eğer hiç bulunamadıysa verimlilik %0'dır.
        if matched and position and total_lines > 0:
            efficiency = round((1.0 - (position / total_lines)) * 100.0, 2)
        else:
            efficiency = 0.0

        return {
            "mode": mode_name,
            "file": str(wordlist_path.name),
            "status": "MATCHED" if matched else "NO_MATCH",
            "matched": matched,
            "matched_password": audit_result.matched_password,
            "position": position,
            "total_candidates": total_lines,
            "tested_candidates": audit_result.total_tested,
            "duration_seconds": duration,
            "hashes_per_second": rate,
            "efficiency_score": efficiency
        }

    def run_comparative_benchmark(
        self,
        target_hash: str,
        default_path: Path,
        targeted_path: Path,
        hybrid_path: Path,
        target_profile_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Default, AI Targeted ve Hybrid listelerini aynı hedef hash üzerinde yarıştırır
        ve sonuçları JSON raporu olarak kaydeder.
        """
        logger.info(f"Karşılaştırmalı benchmark başladı -> Hedef Hash: {target_hash[:12]}...")
        start_dt = datetime.now(timezone.utc)

        results: List[Dict[str, Any]] = []

        # 1. Varsayılan Liste
        res_default = self.run_single_benchmark("VARSAYILAN (Default)", default_path, target_hash)
        results.append(res_default)

        # 2. AI Hedefli Liste
        res_targeted = self.run_single_benchmark("AI HEDEFLİ (Targeted)", targeted_path, target_hash)
        results.append(res_targeted)

        # 3. Hibrit Liste
        res_hybrid = self.run_single_benchmark("HİBRİT (Hybrid)", hybrid_path, target_hash)
        results.append(res_hybrid)

        # Kazananı belirle
        winner = None
        min_pos = float("inf")
        for r in results:
            if r["matched"] and r["position"] and r["position"] < min_pos:
                min_pos = r["position"]
                winner = r["mode"]

        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"benchmark_{timestamp_slug}.json"
        report_path = self.reports_dir / report_filename

        report_data: Dict[str, Any] = {
            "title": "Smart Password Auditor - Benchmark Karşılaştırma Raporu",
            "timestamp": start_dt.isoformat(),
            "target_hash": target_hash,
            "target_profile": target_profile_name or "Bilinmeyen Hedef",
            "winner_mode": winner or "Hiçbiri eşleşmedi",
            "benchmark_results": results
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Benchmark tamamlandı. Rapor kaydedildi: {report_path.name}")
        return {
            "report_path": report_path,
            "report_data": report_data
        }
