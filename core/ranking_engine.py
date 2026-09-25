"""
Cybzenor - Skorlama ve Önceliklendirme Motoru (Ranking Engine)
Adayları semantik yakınlık, ilişki, tarih ve leetspeak ağırlıklarına göre skorlar,
önceliklendirir ve wordlist üretim akışını yönetir.
"""

from pathlib import Path
from typing import Generator, Iterable, List, Tuple, Dict, Any, Optional
from datetime import datetime, timezone
import itertools
import json

from ai.schemas import TargetProfile, PasswordPolicy
from core.candidate_generator import CandidateGenerator, expand_date_variations
from core.wordlist_manager import wordlist_manager
from config.settings import settings, BASE_DIR
from utils.logger import logger


class RankingEngine:
    """
    Parola adaylarını şartname kriterlerine göre skorlayan ve önceliklendiren motor.
    
    Skorlama Kriterleri:
    - Priority 1 (Skor: 90 - 100): Doğrudan hedef isim + yıl kombinasyonları, ilişki ikilileri, temel insan ekleri (örn: Ahmet123, AliSevda2021)
    - Priority 2 (Skor: 50 - 75) : Genel ek almış varyasyonlar (örn: Ali1234, Sevda!) ve ilgi alanı kombinasyonları
    - Priority 3 (Skor: 10 - 30) : Ağır Leetspeak ve karmaşık mutasyonlar (örn: @l1_2021)
    """

    def __init__(self, profile: TargetProfile, policy: Optional[PasswordPolicy] = None) -> None:
        self.profile = profile
        self.policy = policy
        self.names_lower = {n.lower() for n in profile.names}
        self.dates = set(expand_date_variations(profile.dates))
        self.interests_lower = {i.lower() for i in profile.interests}

        # İlişki çiftleri (Profil ikilileri + İsimler arası permütasyonlar)
        self.effective_relations: List[Tuple[str, str]] = []
        for pair in profile.relations:
            if len(pair) >= 2:
                self.effective_relations.append((pair[0].lower(), pair[1].lower()))
                self.effective_relations.append((pair[1].lower(), pair[0].lower()))

        all_names = list(dict.fromkeys([n.lower() for n in profile.names]))
        for p1, p2 in itertools.permutations(all_names, 2):
            if (p1, p2) not in self.effective_relations:
                self.effective_relations.append((p1, p2))

        # AI veya akıllı sezgisel modelden hedefe özel semantik kökleri al
        from ai.ai_manager import get_active_ai_provider
        provider = get_active_ai_provider()
        self.semantic_roots = provider.generate_semantic_password_roots(profile)

        # İlgi alanı/kişilik çağrışım kelimeleri (örn: kahve -> latte) de kök gibi işlenir:
        # isimle birleştirilmez, tek başına veya tarih/ek ile kullanılır (Tier 0 mantığı).
        if profile.association_words:
            self.semantic_roots = list(dict.fromkeys(self.semantic_roots + profile.association_words))

        self.semantic_roots_lower = {r.lower() for r in self.semantic_roots}

    def calculate_score(self, candidate: str) -> int:
        """
        Tek bir parola adayının öncelik skorunu (0 - 100) hesaplar.
        """
        cand_lower = candidate.lower()
        score = 20  # Taban skor

        # 1. İlişki çifti tespiti (AliSevda, AhmetPamuk vb.)
        is_relation = False
        for p1, p2 in self.effective_relations:
            if p1 in cand_lower and p2 in cand_lower:
                is_relation = True
                break

        # AI / Semantik köklerin tam veya doğrudan ekli halleri
        if cand_lower in self.semantic_roots_lower:
            return 98

        has_name = any(name in cand_lower for name in self.names_lower)
        has_date = any(date in candidate for date in self.dates)
        has_interest = any(interest in cand_lower for interest in self.interests_lower)
        has_leet = any(char in candidate for char in ['@', '4', '3', '1', '!', '$', '5', '0'])

        # Priority 1: Doğrudan hedef isim + yıl veya ilişki ikilisi
        if (has_name and has_date) or is_relation:
            score = 95
            if candidate.endswith("!"):
                score += 3
        # Priority 2: İsim + Genel/İnsan Ekleri veya İlgi alanı + Tarih
        elif has_name or (has_interest and has_date):
            score = 65
            if any(cand_lower.endswith(s) for s in ['123', '!', '1', '34', '123!', '1!']):
                score += 10
        # Priority 3: Sadece Leetspeak mutasyonu veya zayıf eşleşmeler
        elif has_leet:
            score = 25
        else:
            score = 35

        return min(score, 100)

    def generate_ranked_candidates(self) -> Generator[str, None, None]:
        """
        CandidateGenerator ile üretilen adayları katmanlı akış (Tier 0 -> Tier 1 -> Tier 2 -> Tier 3)
        mantığıyla sıralı olarak akıtır. Bellek şişmesi yaşanmaz.
        """
        generator = CandidateGenerator(self.profile, semantic_roots=self.semantic_roots, policy=self.policy)
        yield from generator.generate_all()

    def build_targeted_wordlist(self, output_filename: Optional[str] = None) -> Tuple[Path, Dict[str, Any]]:
        """
        Hedef odaklı wordlist dosyasını ve metadata özetini üretir.
        Dosya: wordlists/generated/<filename>.txt
        """
        generated_dir = BASE_DIR / "wordlists" / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        if not output_filename:
            target_slug = self.profile.names[0] if self.profile.names else "target"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"ai_targeted_{target_slug.lower()}_{timestamp}.txt"

        # Güvenlik: output_filename bir AI tarafından (yerel model) serbest metinden
        # çıkarılan bir isme dayanıyor olabilir. Path(...).name, olası "../" veya dizin
        # ayraçlarını atıp sadece son bileşeni alarak generated_dir dışına yazmayı engeller.
        output_filename = Path(output_filename).name or "wordlist.txt"
        output_path = generated_dir / output_filename
        metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")

        logger.info(f"AI Hedefli wordlist üretimi başladı -> {output_filename}")
        start_time = datetime.now(timezone.utc)

        written_count = 0
        priority_1_count = 0
        priority_2_count = 0
        priority_3_count = 0

        with open(output_path, "w", encoding="utf-8") as f:
            for candidate in self.generate_ranked_candidates():
                score = self.calculate_score(candidate)
                if score >= 85:
                    priority_1_count += 1
                elif score >= 50:
                    priority_2_count += 1
                else:
                    priority_3_count += 1

                f.write(candidate + "\n")
                written_count += 1
                if written_count >= settings.wordlist.max_candidates:
                    break

        end_time = datetime.now(timezone.utc)
        duration = round((end_time - start_time).total_seconds(), 4)
        file_size = output_path.stat().st_size if output_path.exists() else 0

        target_name = self.profile.names[0].lower() if self.profile.names else "target"
        policy_desc = self.policy.summary() if self.policy else "Varsayılan (Min 6, Max 32, Serbest)"
        metadata: Dict[str, Any] = {
            "type": "AI_TARGETED",
            "target_id": target_name,
            "output_file": output_path.name,
            "password_policy": policy_desc,
            "target_profile_summary": self.profile.to_summary_dict(),
            "target_profile_details": self.profile.to_detailed_dict(),
            "created_at": end_time.isoformat(),
            "duration_seconds": duration,
            "total_candidates": written_count,
            "below_recommended_minimum": written_count < settings.wordlist.min_candidates,
            "priority_distribution": {
                "priority_1_high": priority_1_count,
                "priority_2_medium": priority_2_count,
                "priority_3_low": priority_3_count
            },
            "file_size_bytes": file_size
        }

        with open(metadata_path, "w", encoding="utf-8") as mf:
            json.dump(metadata, mf, indent=2, ensure_ascii=False)

        logger.info(f"AI Hedefli wordlist tamamlandı: {written_count:,} aday üretildi. Süre: {duration}sn")
        return output_path, metadata

    def build_hybrid_wordlist(
        self,
        default_wordlist_path: Optional[Path] = None,
        output_filename: Optional[str] = None
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Hibrit Wordlist:
        1. Önce hedefe özel AI listesi (en yüksek olasılıklı öncelikli şifreler).
        2. Ardından genel varsayılan şifre listesi (default.txt).
        Tekilleştirilerek tek dosyada birleştirilir.
        """
        generated_dir = BASE_DIR / "wordlists" / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        def_path = default_wordlist_path or (BASE_DIR / "wordlists" / "default.txt")
        if not def_path.is_file():
            raise FileNotFoundError(f"Varsayılan liste bulunamadı: {def_path}")

        if not output_filename:
            target_slug = self.profile.names[0] if self.profile.names else "target"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"hybrid_{target_slug.lower()}_{timestamp}.txt"

        # Güvenlik: bkz. build_targeted_wordlist'teki aynı not — AI kaynaklı isimler
        # generated_dir dışına path traversal ile yazamasın diye sadece dosya adı alınır.
        output_filename = Path(output_filename).name or "wordlist.txt"
        output_path = generated_dir / output_filename
        metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")

        logger.info(f"Hibrit wordlist üretimi başladı -> {output_filename}")
        start_time = datetime.now(timezone.utc)

        seen = set()
        targeted_count = 0
        default_count = 0

        with open(output_path, "w", encoding="utf-8") as out:
            # 1. Aşama: AI Hedefli listeyi yaz
            for candidate in self.generate_ranked_candidates():
                lookup = candidate if settings.wordlist.case_sensitive_dedup else candidate.lower()
                if lookup not in seen:
                    seen.add(lookup)
                    out.write(candidate + "\n")
                    targeted_count += 1
                    if targeted_count >= settings.wordlist.max_candidates:
                        break

            # 2. Aşama: Varsayılan (default.txt) listeyi streaming ile ekle
            for default_pwd in wordlist_manager.stream_lines(def_path):
                # Politika veya uzunluk filtresi
                if self.policy:
                    if not self.policy.is_satisfied(default_pwd):
                        continue
                else:
                    if not (settings.wordlist.min_length <= len(default_pwd) <= settings.wordlist.max_length):
                        continue

                lookup = default_pwd if settings.wordlist.case_sensitive_dedup else default_pwd.lower()
                if lookup not in seen:
                    seen.add(lookup)
                    out.write(default_pwd + "\n")
                    default_count += 1

        end_time = datetime.now(timezone.utc)
        duration = round((end_time - start_time).total_seconds(), 4)
        total_written = targeted_count + default_count

        target_name = self.profile.names[0].lower() if self.profile.names else "target"
        policy_desc = self.policy.summary() if self.policy else "Varsayılan (Min 6, Max 32, Serbest)"
        metadata: Dict[str, Any] = {
            "type": "HYBRID",
            "target_id": target_name,
            "output_file": output_path.name,
            "password_policy": policy_desc,
            "target_profile_summary": self.profile.to_summary_dict(),
            "target_profile_details": self.profile.to_detailed_dict(),
            "created_at": end_time.isoformat(),
            "duration_seconds": duration,
            "total_candidates": total_written,
            "targeted_candidates": targeted_count,
            "default_candidates": default_count,
            "below_recommended_minimum": total_written < settings.wordlist.min_candidates,
            "file_size_bytes": output_path.stat().st_size if output_path.exists() else 0
        }

        with open(metadata_path, "w", encoding="utf-8") as mf:
            json.dump(metadata, mf, indent=2, ensure_ascii=False)

        logger.info(f"Hibrit wordlist tamamlandı: {total_written:,} aday (AI: {targeted_count}, Default: {default_count})")
        return output_path, metadata
