"""
Cybzenor GUI - Arayüz/Çekirdek Köprüsü
GUI sayfalarının core/ ve ai/ modüllerine erişimini tek yerden sağlayan, tkinter'dan
bağımsız (test edilebilir) yardımcı fonksiyonlar. main.py'deki CLI akışlarıyla AYNI
disk formatını (data/synthetic_profiles/*.json) kullanır; GUI ve CLI ile üretilen
hedefler birbirinden bağımsız olarak karışık kullanılabilir.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.ai_manager import get_active_ai_provider
from ai.schemas import PasswordPolicy, TargetProfile
from config.settings import BASE_DIR
from core.hash_audit_engine import AuditResult, LocalHashAuditEngine, test_engine
from core.ranking_engine import RankingEngine
from core.safety_controller import MockAuthService, SafetyController, run_safety_monitored_audit
from core.wordlist_manager import wordlist_manager
from utils.turkish_data import TR_CLUB_FOUNDING_YEARS

SYNTHETIC_DIR = BASE_DIR / "data" / "synthetic_profiles"
GENERATED_DIR = wordlist_manager.generated_dir
DEFAULT_WORDLIST = wordlist_manager.default_wordlist_path

HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def is_sha256_hex(value: str) -> bool:
    return bool(HEX64_RE.match(value.strip()))


def compute_sha256(plain_text: str) -> str:
    return LocalHashAuditEngine.compute_hash_sha256(plain_text)


def resolve_hash_input(value: str) -> str:
    """Kullanıcının girdiği metnin zaten bir SHA-256 hash mi yoksa açık parola mı
    olduğunu tespit edip her durumda geçerli bir hedef hash döner."""
    value = value.strip()
    return value.lower() if is_sha256_hex(value) else compute_sha256(value)


# --------------------------------------------------------------------------------------
# Hedef Profil (Target) Yönetimi
# --------------------------------------------------------------------------------------

@dataclass
class TargetRecord:
    """data/synthetic_profiles/*.json içeriğini temsil eden hafif veri sınıfı."""
    path: Path
    target_id: str
    target_name: str
    profile: TargetProfile
    plain_password_hint: str = ""
    target_hash: str = ""

    @property
    def has_hash(self) -> bool:
        return bool(self.target_hash)


def list_target_records() -> List[TargetRecord]:
    """Kayıtlı tüm hedef profillerini (en yeniden en eskiye) döner. Bozuk dosyalar atlanır."""
    if not SYNTHETIC_DIR.is_dir():
        return []
    records: List[TargetRecord] = []
    files = sorted(SYNTHETIC_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            gt = data.get("ground_truth") or {}
            records.append(TargetRecord(
                path=f,
                target_id=data.get("target_id", f.stem),
                target_name=data.get("target_name", f.stem),
                profile=TargetProfile(**data.get("profile", {})),
                plain_password_hint=gt.get("plain_password_hint", ""),
                target_hash=gt.get("target_hash", ""),
            ))
        except Exception:
            continue
    return records


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", text.lower()).strip("_")
    return slug or "target"


def save_target_record(
    target_name: str,
    profile: TargetProfile,
    plain_password_hint: str = "",
) -> Path:
    """Hedef profilini data/synthetic_profiles/ altına kaydeder (CLI ile aynı format)."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(target_name or (profile.names[0] if profile.names else "target"))
    slug_file = SYNTHETIC_DIR / f"target_{slug}.json"

    target_hash = compute_sha256(plain_password_hint) if plain_password_hint else ""
    data = {
        "target_id": f"target_{slug}",
        "target_name": target_name or slug,
        "profile": profile.to_detailed_dict(),
        "ground_truth": {
            "plain_password_hint": plain_password_hint or f"{target_name or slug} hedef profili",
            "hash_type": "sha256",
            "target_hash": target_hash,
        },
    }
    with open(slug_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return slug_file


def delete_target_record(path: Path) -> None:
    if path.is_file():
        path.unlink()


def apply_club_founding_years(interests: List[str], dates: List[str]) -> List[str]:
    """Bilinen bir kulüp ilgi alanı girildiyse kuruluş yılını tarihlere ekler (CLI davranışıyla aynı)."""
    merged = set(dates)
    for interest in interests:
        key = interest.strip().lower()
        if key in TR_CLUB_FOUNDING_YEARS:
            merged.add(TR_CLUB_FOUNDING_YEARS[key])
    return sorted(merged)


def build_profile_from_form(
    names: List[str],
    dates: List[str],
    locations: List[str],
    interests: List[str],
    keywords: List[str],
) -> TargetProfile:
    dates = apply_club_founding_years(interests, dates)
    relations: List[List[str]] = []
    if len(names) >= 2:
        relations.append([names[0], names[1]])
    return TargetProfile(
        names=names, dates=dates, locations=locations,
        interests=interests, relations=relations, keywords=keywords,
    )


def enrich_profile_with_free_text(profile: TargetProfile, free_text: str) -> TargetProfile:
    """Serbest metni AI (yerel model veya kural motoru) ile çözümleyip mevcut profille birleştirir."""
    if not free_text.strip():
        return profile
    provider = get_active_ai_provider()
    parsed = provider.extract_target_profile(free_text)

    names = sorted(set(profile.names) | set(parsed.names))
    dates = sorted(set(profile.dates) | set(parsed.dates))
    locations = sorted(set(profile.locations) | set(parsed.locations))
    interests = sorted(set(profile.interests) | set(parsed.interests))
    keywords = sorted(set(profile.keywords) | set(parsed.keywords))
    relations = profile.relations or ([[names[0], names[1]]] if len(names) >= 2 else [])

    return TargetProfile(
        names=names, dates=dates, locations=locations, interests=interests,
        relations=relations, keywords=keywords, association_words=parsed.association_words,
    )


def ai_engine_status() -> Dict[str, Any]:
    provider = get_active_ai_provider()
    return {
        "available": provider.is_available(),
        "label": provider.PROVIDER_LABEL,
    }


def ai_setup_hint() -> str:
    """
    Kullanıcıya yerel AI'yı nasıl kuracağını söyleyen kısa metin. .exe (donmuş) modda
    çalışan kullanıcının Python'u kurulu OLMAYABİLİR — bu yüzden 'python setup_local_ai.py'
    komutu yerine uygulama içindeki 'Ayarlar' sayfasına yönlendirilir. Kaynak koddan
    (python launch_gui.py ile) çalışırken komut önerilir.
    """
    if getattr(sys, "frozen", False):
        return "Ayarlar sayfasından 'Yerel AI Modelini Kur' butonuna tıklayın"
    return "'python setup_local_ai.py' çalıştırın"


# --------------------------------------------------------------------------------------
# Wordlist Üretimi
# --------------------------------------------------------------------------------------

def safe_wordlist_filename(name: str, default_prefix: str = "wordlist") -> str:
    """Kullanıcı girdisinden güvenli (path traversal olmayan), .txt uzantılı dosya adı üretir."""
    name = (name or "").strip()
    if not name:
        name = f"{default_prefix}_{Path.cwd().stat().st_mtime_ns}"
    safe = Path(name).name or default_prefix
    return safe if safe.lower().endswith(".txt") else f"{safe}.txt"


def generate_targeted_wordlist(profile: TargetProfile, policy: Optional[PasswordPolicy], filename: str):
    engine = RankingEngine(profile, policy=policy)
    return engine.build_targeted_wordlist(output_filename=filename)


def list_all_wordlists() -> List[Path]:
    """Varsayılan liste + tüm üretilmiş listeleri (en yeniden en eskiye) döner."""
    options: List[Path] = []
    if DEFAULT_WORDLIST.is_file():
        options.append(DEFAULT_WORDLIST)
    if GENERATED_DIR.is_dir():
        options.extend(sorted(GENERATED_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True))
    return options


def wordlist_line_count(path: Path) -> int:
    try:
        return wordlist_manager.get_wordlist_stats(path)["total_lines"]
    except Exception:
        return 0


def merge_wordlists_hybrid(sources: List[Path], output_filename: str, case_sensitive: bool) -> Dict[str, Any]:
    output_path = GENERATED_DIR / safe_wordlist_filename(output_filename, "hybrid")
    return wordlist_manager.merge_wordlists(source_paths=sources, output_path=output_path, case_sensitive=case_sensitive)


# --------------------------------------------------------------------------------------
# Hash Denetim
# --------------------------------------------------------------------------------------

def run_hash_audit(target_hash: str, wordlist_path: Path) -> AuditResult:
    return test_engine.audit_wordlist_stream(target_hash=target_hash, wordlist_path=wordlist_path)


# --------------------------------------------------------------------------------------
# Online Login Audit (yardımcılar; HTTP çağrıları core/online_login_auditor.py'de kalır)
# --------------------------------------------------------------------------------------

MOCK_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "rate_limit": dict(label="Rate-Limit Simülasyonu (HTTP 429)", target_password="NON_EXISTENT_PWD", rate_limit_after=15, delay_ms=15),
    "lockout": dict(label="Hesap Kilitleme Simülasyonu (423)", target_password="NON_EXISTENT_PWD", lockout_after_failures=10, delay_ms=15),
    "captcha": dict(label="CAPTCHA / Bot Doğrulama Tespiti", target_password="NON_EXISTENT_PWD", captcha_after=12, delay_ms=15),
    "max_failures": dict(label="Maksimum Ardışık Başarısızlık Eşiği", target_password="NON_EXISTENT_PWD", delay_ms=5),
    "safe_match": dict(label="Güvenli Eşleşme (limit aşılmadan bulma)", target_password="password", rate_limit_after=50, delay_ms=15),
}


def run_mock_scenario(scenario_key: str, wordlist_path: Path) -> Dict[str, Any]:
    """SafetyController demo senaryolarını (rate-limit/lockout/captcha/…) statik wordlist ile koşturur."""
    params = dict(MOCK_SCENARIOS[scenario_key])
    params.pop("label", None)
    service = MockAuthService(**params)
    return run_safety_monitored_audit(wordlist_path=wordlist_path, mock_service=service)


def run_live_login_audit(
    service,
    wordlist_path: Path,
    max_consecutive_failures: int,
    exclude_passwords: Optional[set] = None,
    start_index: int = 0,
) -> Dict[str, Any]:
    """Canlı (gerçek HTTP) login denetimini SafetyController gözetiminde bir tur koşturur."""
    return run_safety_monitored_audit(
        wordlist_path=wordlist_path,
        mock_service=service,
        safety_controller=SafetyController(max_consecutive_failures=max_consecutive_failures),
        exclude_passwords=exclude_passwords,
        start_index=start_index,
    )
