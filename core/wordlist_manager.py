"""
Cybzenor - Wordlist Yöneticisi
Düşük RAM kullanımı için streaming (generator) dosya I/O, tekilleştirme,
karakter uzunluğu filtreleme ve metadata yönetim motoru.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Iterable, Dict, Any, Optional, Set, Tuple, List

from config.settings import settings, BASE_DIR
from utils.logger import logger


class WordlistManager:
    """Wordlist dosyalarını streaming yöntemiyle okuyan, filtreleyen ve kaydeden yönetici."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or BASE_DIR
        self.wordlists_dir = self.base_dir / "wordlists"
        self.default_wordlist_path = self.wordlists_dir / "default.txt"
        self.generated_dir = self.wordlists_dir / "generated"

        # Dizinlerin varlığını garanti altına al
        self.wordlists_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def stream_lines(file_path: Path, encoding: str = "utf-8") -> Generator[str, None, None]:
        """
        Dosyayı satır satır akıtarak (yield) okur.
        Bellekte (RAM) tüm dosyayı tutmaz; bu sayede devasa boyutlu listelerde dahi O(1) RAM tüketir.
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"Wordlist dosyası bulunamadı: {file_path}")

        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned:  # Boş satırları atla
                    yield cleaned

    @staticmethod
    def filter_and_deduplicate(
        candidates: Iterable[str],
        min_length: int = 6,
        max_length: int = 32,
        case_sensitive: bool = False,
        char_rule: str = "all"
    ) -> Generator[str, None, None]:
        """
        Verilen aday akışını uzunluk kriterlerine ve karakter kurallarına göre filtreler ve mükerrer kayıtları tekilleştirir.
        char_rule:
          - "all": Tüm karakter kombinasyonları
          - "digit": En az 1 rakam içermeli
          - "alphanumeric": En az 1 harf ve 1 rakam içermeli
          - "numeric_only": Sadece rakamlardan oluşmalı (PIN/Sayısal)
          - "special": En az 1 özel karakter içermeli
        """
        seen: Set[str] = set()

        for candidate in candidates:
            # 1. Uzunluk kontrolü
            if not (min_length <= len(candidate) <= max_length):
                continue

            # 2. Karakter kuralları
            if char_rule == "digit":
                if not any(c.isdigit() for c in candidate):
                    continue
            elif char_rule == "alphanumeric":
                has_alpha = any(c.isalpha() for c in candidate)
                has_digit = any(c.isdigit() for c in candidate)
                if not (has_alpha and has_digit):
                    continue
            elif char_rule == "numeric_only":
                if not candidate.isdigit():
                    continue
            elif char_rule == "special":
                if not any(not c.isalnum() for c in candidate):
                    continue

            # 3. Tekilleştirme kontrolü
            lookup_key = candidate if case_sensitive else candidate.lower()
            if lookup_key in seen:
                continue

            seen.add(lookup_key)
            yield candidate

    def process_and_save(
        self,
        source_path: Path,
        output_path: Path,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        case_sensitive: Optional[bool] = None,
        char_rule: str = "all"
    ) -> Dict[str, Any]:
        """
        Bir kaynak dosyayı okur, filtreleyip tekilleştirerek hedef dosyaya yazar ve
        yanında bir .metadata.json dosyası oluşturur.
        """
        min_len = min_length if min_length is not None else settings.wordlist.min_length
        max_len = max_length if max_length is not None else settings.wordlist.max_length
        case_sens = case_sensitive if case_sensitive is not None else settings.wordlist.case_sensitive_dedup

        logger.info(
            f"Wordlist işleme başladı: Kaynak={source_path.name}, Min={min_len}, Max={max_len}, Duyarlılık={case_sens}, Kural={char_rule}"
        )

        total_lines = 0
        written_lines = 0
        filtered_out = 0

        # Hedef dizini garanti et
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now(timezone.utc)

        # Yazma işlemi
        with open(output_path, "w", encoding="utf-8") as out_file:
            stream = self.stream_lines(source_path)
            filtered_stream = self.filter_and_deduplicate(
                candidates=stream,
                min_length=min_len,
                max_length=max_len,
                case_sensitive=case_sens,
                char_rule=char_rule
            )

            for line in filtered_stream:
                out_file.write(line + "\n")
                written_lines += 1

        # Kaynak dosya toplam satırını say
        for _ in self.stream_lines(source_path):
            total_lines += 1

        filtered_out = total_lines - written_lines
        file_size_bytes = output_path.stat().st_size if output_path.exists() else 0
        end_time = datetime.now(timezone.utc)

        metadata: Dict[str, Any] = {
            "source_file": source_path.name,
            "output_file": output_path.name,
            "created_at": end_time.isoformat(),
            "duration_seconds": round((end_time - start_time).total_seconds(), 4),
            "total_source_lines": total_lines,
            "unique_written_lines": written_lines,
            "filtered_or_duplicate_lines": filtered_out,
            "file_size_bytes": file_size_bytes,
            "filters": {
                "min_length": min_len,
                "max_length": max_len,
                "case_sensitive_dedup": case_sens,
                "char_rule": char_rule
            }
        }

        # Metadata dosyasını kaydet (örn: wordlist.txt -> wordlist.metadata.json)
        metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(metadata, meta_file, indent=2, ensure_ascii=False)

        logger.info(
            f"Wordlist işleme tamamlandı: {written_lines:,} benzersiz parola kaydedildi ({filtered_out:,} elendi). "
            f"Metadata: {metadata_path.name}"
        )

        return metadata

    def get_wordlist_stats(self, file_path: Path) -> Dict[str, Any]:
        """
        Belirtilen wordlist dosyasının satır sayısı, boyutu ve varsa metadata bilgilerini döndürür.
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

        line_count = 0
        min_len = float("inf")
        max_len = 0

        for line in self.stream_lines(file_path):
            line_count += 1
            length = len(line)
            if length < min_len:
                min_len = length
            if length > max_len:
                max_len = length

        stats: Dict[str, Any] = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "file_size_bytes": file_path.stat().st_size,
            "total_lines": line_count,
            "min_length": int(min_len) if line_count > 0 else 0,
            "max_length": int(max_len) if line_count > 0 else 0,
        }

        # Varsa metadata dosyasını yükle
        meta_path = file_path.with_suffix(file_path.suffix + ".metadata.json")
        if meta_path.is_file():
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    stats["metadata"] = json.load(mf)
            except Exception:
                pass

        return stats

    def list_generated_wordlists(self) -> List[Dict[str, Any]]:
        """
        Üretilen (generated) tüm wordlist dosyalarını en yeniden en eskiye listeler.
        """
        results = []
        if not self.generated_dir.exists():
            return results

        txt_files = sorted(self.generated_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in txt_files:
            stat = f.stat()
            meta_path = f.with_suffix(f.suffix + ".metadata.json")
            meta = None
            if meta_path.is_file():
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                except Exception:
                    pass

            results.append({
                "name": f.name,
                "path": f,
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
                "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "total_candidates": meta.get("total_candidates") if meta else None,
                "type": meta.get("type") if meta else "CUSTOM",
                "metadata": meta
            })
        return results

    def get_head(self, file_path: Path, n: int = 10) -> List[Tuple[int, str]]:
        """Dosyanın ilk n satırını satır numarasıyla birlikte döndürür (1-indexed)."""
        lines = []
        for idx, line in enumerate(self.stream_lines(file_path), start=1):
            lines.append((idx, line))
            if len(lines) >= n:
                break
        return lines

    def get_tail(self, file_path: Path, n: int = 10) -> List[Tuple[int, str]]:
        """Dosyanın son n satırını satır numarasıyla birlikte döndürür."""
        from collections import deque
        dq: deque[Tuple[int, str]] = deque(maxlen=n)
        for idx, line in enumerate(self.stream_lines(file_path), start=1):
            dq.append((idx, line))
        return list(dq)

    def search_lines(self, file_path: Path, query: str, max_results: int = 50) -> List[Tuple[int, str]]:
        """Belirtilen sorguyu içeren satırları arar."""
        q_lower = query.lower()
        matches = []
        for idx, line in enumerate(self.stream_lines(file_path), start=1):
            if q_lower in line.lower():
                matches.append((idx, line))
                if len(matches) >= max_results:
                    break
        return matches


# Global wordlist yöneticisi örneği
wordlist_manager = WordlistManager()
