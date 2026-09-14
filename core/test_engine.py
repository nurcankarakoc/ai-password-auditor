"""
Smart Password Auditor (SPA) - Yerel Hash Denetim Motoru (Local Hash Audit Engine)
Wordlist adaylarını streaming ile okuyup yerel hedef SHA-256 hash'leri üzerinde
doğrulayan, denetim pozisyonunu ve sürelerini ölçen motor.
"""

import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, Generator, Tuple
from pydantic import BaseModel, Field

from core.wordlist_manager import wordlist_manager
from utils.logger import logger


class AuditResult(BaseModel):
    """Denetim sonucunu içeren veri modeli."""
    matched: bool = Field(default=False, description="Parola eşleşti mi?")
    matched_password: Optional[str] = Field(default=None, description="Bulunan açık parola")
    target_hash: str = Field(description="Hedeflenen hash değeri")
    hash_type: str = Field(default="sha256", description="Kullanılan hash algoritması")
    position: int = Field(default=0, description="Eşleşmenin bulunduğu sıra (1-indexed)")
    total_tested: int = Field(default=0, description="Test edilen toplam aday sayısı")
    duration_seconds: float = Field(default=0.0, description="Geçen toplam süre (saniye)")
    hashes_per_second: float = Field(default=0.0, description="Saniyede hesaplanan ortalama hash hızı")
    wordlist_name: str = Field(default="", description="Kullanılan wordlist dosya adı")


class LocalHashAuditEngine:
    """Yerel laboratuvar ve sentetik test ortamı için hash kıyaslama motoru."""

    def __init__(self, hash_type: str = "sha256") -> None:
        self.hash_type = hash_type.lower()
        if self.hash_type not in hashlib.algorithms_guaranteed:
            raise ValueError(f"Desteklenmeyen hash algoritması: {self.hash_type}")

    @staticmethod
    def compute_hash_sha256(candidate: str) -> str:
        """SHA-256 hash değerini doğrudan hesaplar."""
        return hashlib.sha256(candidate.encode("utf-8")).hexdigest()

    def compute_hash(self, candidate: str) -> str:
        """Verilen adayın hash değerini hesaplar."""
        hasher = hashlib.new(self.hash_type)
        hasher.update(candidate.encode("utf-8"))
        return hasher.hexdigest()

    def audit_wordlist_stream(
        self,
        target_hash: str,
        wordlist_path: Path,
        max_attempts: Optional[int] = None
    ) -> AuditResult:
        """
        Wordlist dosyasını satır satır streaming okuyarak hedef hash ile kıyaslar.
        Eşleşme bulunduğu an döngüyü derhal sonlandırır.
        """
        clean_target = target_hash.strip().lower()
        logger.info(f"Yerel denetim başladı. Hedef: {clean_target[:8]}... Dosya: {wordlist_path.name}")

        start_time = time.perf_counter()
        tested_count = 0
        matched = False
        matched_password = None
        match_position = 0

        for candidate in wordlist_manager.stream_lines(wordlist_path):
            tested_count += 1
            cand_hash = self.compute_hash(candidate)

            if cand_hash == clean_target:
                matched = True
                matched_password = candidate
                match_position = tested_count
                break

            if max_attempts and tested_count >= max_attempts:
                break

        end_time = time.perf_counter()
        duration = max(end_time - start_time, 0.000001)
        hps = round(tested_count / duration, 2)

        if matched:
            logger.info(
                f"Parola bulundu! Pozisyon: {match_position:,}, Süre: {duration:.4f}sn, Hız: {hps:,} h/s"
            )
        else:
            logger.info(f"Eşleşme bulunamadı. Toplam {tested_count:,} aday denendi. Süre: {duration:.4f}sn")

        return AuditResult(
            matched=matched,
            matched_password=matched_password,
            target_hash=clean_target,
            hash_type=self.hash_type,
            position=match_position,
            total_tested=tested_count,
            duration_seconds=round(duration, 4),
            hashes_per_second=hps,
            wordlist_name=wordlist_path.name
        )


# Global motor örneği
test_engine = LocalHashAuditEngine(hash_type="sha256")
