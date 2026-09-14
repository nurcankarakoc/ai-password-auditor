"""
Smart Password Auditor (SPA) - Deterministik Kural Motoru (Candidate Generator)
Yapılandırılmış TargetProfile nesnesinden hafızayı (RAM) şişirmeden
akışkan (yield/generator) ve aşamalı (Tiered) parola adayları üreten motor.
"""

import re
import itertools
from typing import Generator, List, Set, Tuple, Optional
from ai.schemas import TargetProfile, PasswordPolicy
from config.settings import settings


# Sıkı sınırlandırılmış Leetspeak haritası (Şartname: a->@/4, e->3, i->1/!, s->5/$)
LEET_MAP = {
    'a': ['@', '4'],
    'e': ['3'],
    'i': ['1', '!'],
    's': ['5', '$'],
    'o': ['0'],
}

# Türkçe karakter ASCII normalizasyon haritası
TR_NORMALIZE_MAP = str.maketrans({
    'ç': 'c', 'Ç': 'C',
    'ğ': 'g', 'Ğ': 'G',
    'ı': 'i', 'I': 'I', 'İ': 'I', 'i': 'i',
    'ö': 'o', 'Ö': 'O',
    'ş': 's', 'Ş': 'S',
    'ü': 'u', 'Ü': 'U'
})

DELIMITERS = ['', '_', '.', '-', '*', '+']
SPECIAL_CHARS = ['!', '.', '_', '*', '#', '@', '?', '$', '-']
TOP_SPECIALS = ['!', '.', '_', '*', '#', '@']

# İnsanların en çok kullandığı temel/basit son ekler (Nurcan123, Ali1, Sevda123! vb.)
HUMAN_TOP_SUFFIXES = [
    '123', '1', '12', '123!', '!', '1!', '1234', '12345', '123456',
    '2024', '2025', '2026', '2027', 'qwe', 'asdf', '147', '258', '369', '147258',
    '123123', '123321', '112233', '2580', '1903', '1905', '1907', '01', '06', '07', '16', '34', '35', '61'
]

# Genel zengin son ekler
RICH_SUFFIXES = [
    '123', '1234', '12345', '123456', '1234567', '12345678', '1', '12', '!', '1!', '123!',
    '2023', '2024', '2025', '2026', '2027', '2030',
    '01', '02', '03', '06', '07', '16', '34', '35', '41', '42', '55', '61',
    '00', '11', '99', '007', '147', '258', '369', '147258', '2580', '123123', '123321', '112233',
    'qwe', 'asdf', 'zxc', 'pass', 'sifre', 'admin', 'root', 'user'
]

# Kulüp tanımları ve yılları
TURKISH_CLUBS = {
    'fb': {'names': ['fenerbahce', 'fenerbahçe', 'fb', 'kanarya'], 'years': ['1907']},
    'gs': {'names': ['galatasaray', 'gs', 'cimbom'], 'years': ['1905']},
    'bjk': {'names': ['besiktas', 'beşiktaş', 'bjk', 'kartal'], 'years': ['1903']},
    'ts': {'names': ['trabzonspor', 'ts', 'firtina'], 'years': ['1967', '61']},
}

RE_DUPLICATE_YEARS = re.compile(r'(\d{4})[_\.\-]?(\d{4})')


def normalize_turkish(text: str) -> str:
    """Türkçe karakterleri ASCII eşdeğerlerine dönüştürür."""
    return text.translate(TR_NORMALIZE_MAP)


def get_casing_variations(word: str) -> List[str]:
    """
    Bir kelimenin Capitalize (Title), küçük ve BÜYÜK varyasyonlarını
    sıralı ve tekil liste olarak döndürür.
    """
    cleaned = word.strip()
    if not cleaned:
        return []

    forms = [cleaned, normalize_turkish(cleaned)]
    variations = []
    seen_vars = set()

    def add_v(v):
        if v and v not in seen_vars:
            seen_vars.add(v)
            variations.append(v)

    for form in forms:
        # Öncelik sırası: Capitalize -> Lower -> Upper
        add_v(form.capitalize())
        add_v(form.lower())
        add_v(form.upper())

    return variations


def expand_date_variations(raw_dates: List[str]) -> List[str]:
    """
    Kullanıcının girdiği tarihlerden (örn: 2004, 10.10.2004, 1995, 06)
    en yaygın insan parola alışkanlıklarına göre alt parçalar türetir:
    - 2004 -> ['2004', '04', '0404']
    - 10.10.2004 / 10/10/2004 -> ['10.10.2004', '2004', '04', '1010', '10.10', '101004', '10102004', '10.10.04']
    - 1993 -> ['1993', '93', '9393']
    """
    variations = []
    seen = set()

    def add(d: str):
        d_clean = d.strip()
        if d_clean and d_clean not in seen:
            seen.add(d_clean)
            variations.append(d_clean)

    for raw in raw_dates:
        s = raw.strip()
        if not s:
            continue
        add(s)

        # DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY
        m_dmy = re.match(r"^(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})$", s)
        # YYYY.MM.DD
        m_ymd = re.match(r"^(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})$", s)

        if m_dmy:
            day, month, year = m_dmy.groups()
            d2 = f"{int(day):02d}"
            m2 = f"{int(month):02d}"
            y2 = year[-2:]
            y4 = year if len(year) == 4 else f"20{year}"
            add(y4)
            add(y2)
            add(f"{d2}{m2}")
            add(f"{d2}.{m2}")
            add(f"{d2}{m2}{y2}")
            add(f"{d2}{m2}{y4}")
            add(f"{d2}.{m2}.{y2}")
            add(f"{d2}.{m2}.{y4}")
        elif m_ymd:
            year, month, day = m_ymd.groups()
            d2 = f"{int(day):02d}"
            m2 = f"{int(month):02d}"
            y2 = year[-2:]
            y4 = year
            add(y4)
            add(y2)
            add(f"{d2}{m2}")
            add(f"{d2}{m2}{y2}")
            add(f"{d2}{m2}{y4}")
        elif len(s) == 8 and s.isdigit():
            # DDMMYYYY
            d2, m2, y4 = s[:2], s[2:4], s[4:]
            y2 = y4[-2:]
            add(y4)
            add(y2)
            add(f"{d2}{m2}")
            add(f"{d2}{m2}{y2}")
            add(f"{d2}.{m2}.{y4}")
        elif len(s) == 4 and s.isdigit():
            # 4 haneli yıl: 2004 -> 04, 0404
            y2 = s[-2:]
            add(y2)
            add(f"{y2}{y2}")
        elif len(s) == 2 and s.isdigit():
            # 2 haneli yıl veya plaka
            add(f"{s}{s}")
            add(f"20{s}")

    return variations


def apply_leetspeak(word: str, max_variations: int = 4) -> List[str]:
    """
    Kelimeye kontrollü Leetspeak mutasyonu uygular.
    Kombinatoryal patlamayı önlemek için sınırlı varyasyon üretir.
    """
    base_lower = word.lower()
    replacements = []

    for char in base_lower:
        if char in LEET_MAP:
            replacements.append([char] + LEET_MAP[char])
        else:
            replacements.append([char])

    results = set()
    for chars in itertools.islice(itertools.product(*replacements), max_variations + 5):
        variant = "".join(chars)
        if variant != base_lower:
            results.add(variant)
            results.add(variant.capitalize())
            if len(results) >= max_variations:
                break

    return list(results)


class CandidateGenerator:
    """
    Aşamalı (Tiered) ve Akışkan (Generator) Parola Üretim Motoru.
    
    Öncelik Kademeleri:
    - TIER 0 (AI & Semantik Zeka): LLM ve anlamsal modelin hedefin psikolojisine ve takımlarına göre ürettiği akıllı kalıplar
    - TIER 1 (En Yüksek Öncelik): İsim + Temel İnsan Ekleri (123, 1, !), İsim + Yıl (ve alt parçaları), İsim + Ayraç + Yıl,
                                  Tüm İsimler arası Çapraz Kombinasyonlar (AliSevda, SevdaAli, NurcanWinki)
    - TIER 2 (Orta Öncelik)     : İsim/İlişki + Zengin Ekler (1234, 34, 147 vb.),
                                  Hedef Takım + Yıl, İlgi alanları + Ekler, Prefix wraps (!Ali!, _Ali_)
    - TIER 3 (Düşük Öncelik)    : Leetspeak mutasyonları + Tarihler / Ayraçlar / Ekler
    """

    def __init__(
        self,
        profile: TargetProfile,
        semantic_roots: Optional[List[str]] = None,
        policy: Optional[PasswordPolicy] = None
    ) -> None:
        self.profile = profile
        self.policy = policy
        self.semantic_roots = semantic_roots or []
        self.seen: Set[str] = set()

        # Kulüp analizi ve akıllı son ek filtreleme
        profile_text = " ".join(
            profile.names + profile.interests + profile.keywords + profile.dates
        ).lower()

        detected_clubs = []
        for c_key, c_info in TURKISH_CLUBS.items():
            if any(cn in profile_text for cn in c_info['names']) or any(cy in profile_text for cy in c_info['years']):
                detected_clubs.append(c_key)

        # Hedef kulüplere ait yılları ekle, rakip takım yıllarını son eklerden temizle
        active_club_years = set()
        rival_club_years = set()
        for c_key, c_info in TURKISH_CLUBS.items():
            if c_key in detected_clubs:
                active_club_years.update(c_info['years'])
            elif detected_clubs:  # Bilinen bir takım belirtilmişse diğerleri rakip kabul edilir
                rival_club_years.update(c_info['years'])

        base_rich_suffixes = settings.rules.common_suffixes or RICH_SUFFIXES
        filtered_suffixes = [s for s in base_rich_suffixes if s not in rival_club_years]
        for cy in active_club_years:
            if cy not in filtered_suffixes:
                filtered_suffixes.append(cy)

        self.suffixes = filtered_suffixes
        self.active_club_years = list(active_club_years)
        self.rival_club_years = rival_club_years

        # Genişletilmiş ve parçalanmış tarihler (örn: 2004 -> 2004, 04, 0404)
        self.dates = expand_date_variations(profile.dates)

        # Genişletilmiş ve kapsamlı ilişkiler (İsimler, Anahtar Kelimeler, Konumlar, Takımlar)
        self.effective_relations: List[Tuple[str, str]] = []
        for pair in profile.relations:
            if len(pair) >= 2:
                self.effective_relations.append((pair[0], pair[1]))
                self.effective_relations.append((pair[1], pair[0]))

        all_names = list(dict.fromkeys(profile.names))
        for p1, p2 in itertools.permutations(all_names, 2):
            if (p1, p2) not in self.effective_relations:
                self.effective_relations.append((p1, p2))

        # İsimler x Anahtar Kelimeler, İlgi Alanları & Konumlar
        other_tokens = profile.keywords + profile.interests + profile.locations
        for name in all_names:
            for tok in other_tokens:
                if (name, tok) not in self.effective_relations:
                    self.effective_relations.append((name, tok))
                if (tok, name) not in self.effective_relations:
                    self.effective_relations.append((tok, name))

        # Anahtar Kelimeler x Konumlar & İlgi Alanları
        for kw in profile.keywords:
            for loc in profile.locations + profile.interests:
                if (kw, loc) not in self.effective_relations:
                    self.effective_relations.append((kw, loc))

    def _yield_unique(self, candidate: str) -> Generator[str, None, None]:
        """Adayı politika kuralları ve anti-gürültü filtreleri dahilinde tekil olarak akıtır."""
        cand = candidate.strip()
        if not cand:
            return

        # 1. Parola Politikası (PasswordPolicy) kontrolü
        if self.policy:
            if not self.policy.is_satisfied(cand):
                return
        else:
            min_len = settings.wordlist.min_length
            max_len = settings.wordlist.max_length
            if not (min_len <= len(cand) <= max_len):
                return

        # 2. Anti-Noise: Çift yıl tekrarını engelle (örn: 20042004, 2004_2004, 2004.2004)
        m_dup = RE_DUPLICATE_YEARS.search(cand)
        if m_dup and m_dup.group(1) == m_dup.group(2):
            return

        # 3. Anti-Noise: Rakip takım yılı filtresi (Hedef Fenerbahçeliyse 1903 veya 1905 içeren aday üretilmez)
        if self.rival_club_years:
            if any(ry in cand for ry in self.rival_club_years):
                return

        lookup = cand if settings.wordlist.case_sensitive_dedup else cand.lower()
        if lookup not in self.seen:
            self.seen.add(lookup)
            yield cand

    def generate_tier_0_ai_semantic(self) -> Generator[str, None, None]:
        """
        Tier 0: Yapay Zeka / Semantik Köklerin en olası varyasyonları.
        Doğrudan hedefin ilgi alanı ve psikolojik tutarlılığına göredir.
        """
        for root in self.semantic_roots:
            yield from self._yield_unique(root)
            yield from self._yield_unique(root.capitalize())
            yield from self._yield_unique(root.lower())

            # Kök + En yaygın insan ekleri (Kulüp yıllarına duyarlı)
            semantic_suffixes = ['!', '123', '123!', '1', '2024', '2025', '34'] + self.active_club_years
            for s in semantic_suffixes:
                yield from self._yield_unique(f"{root}{s}")
                yield from self._yield_unique(f"{root.capitalize()}{s}")
                for sp in TOP_SPECIALS:
                    yield from self._yield_unique(f"{root}_{s}{sp}")

            # Kök + Tarih varyasyonları
            for d in self.dates:
                yield from self._yield_unique(f"{root}{d}")
                yield from self._yield_unique(f"{root}_{d}")
                for sp in TOP_SPECIALS:
                    yield from self._yield_unique(f"{root}_{d}{sp}")

    def generate_tier_1_high_priority(self) -> Generator[str, None, None]:
        """
        Tier 1: En yüksek olasılıklı adaylar (Doğrudan hedefin isimleri, yılları, ilişkileri ve temel insan şifreleri).
        Örn: Nurcan123, Nurcan, Nurcan2004, Nurcan_04, Nurcan123!, AliSevda2021
        """
        base_words = self.profile.names + self.profile.keywords

        # 1. Temel kelimelerin varyasyonları (İsimler, Anahtar Kelimeler) + Temel İnsan Ekleri + Tarihler
        for word in base_words:
            word_cases = get_casing_variations(word)
            for wc in word_cases:
                # Yalın isim
                yield from self._yield_unique(wc)

                # İnsanların en çok kullandığı temel basit son ekler (Nurcan123, Nurcan1, Nurcan123!, Nurcan!)
                for h_suf in HUMAN_TOP_SUFFIXES:
                    yield from self._yield_unique(f"{wc}{h_suf}")
                    yield from self._yield_unique(f"{wc}_{h_suf}")
                    yield from self._yield_unique(f"{wc}.{h_suf}")
                    if not any(c in h_suf for c in '!@#$%^&*()_+-=[]{}|;:,.<>?'):
                        for sp in TOP_SPECIALS:
                            yield from self._yield_unique(f"{wc}{h_suf}{sp}")
                            yield from self._yield_unique(f"{wc}_{h_suf}{sp}")

                # İsim + Hedef Kulüp Yılı & Özel Karakterler (örn: Krakoç1907, Krakoç_1907!)
                for cy in self.active_club_years:
                    for delim in ['', '_', '.', '-']:
                        yield from self._yield_unique(f"{wc}{delim}{cy}")
                        yield from self._yield_unique(f"{cy}{delim}{wc}")
                    for sp in TOP_SPECIALS:
                        yield from self._yield_unique(f"{wc}{cy}{sp}")
                        yield from self._yield_unique(f"{wc}_{cy}{sp}")
                        yield from self._yield_unique(f"{sp}{wc}{cy}")
                    for date in self.dates:
                        for sp in ['!', '.', '_', '*']:
                            yield from self._yield_unique(f"{wc}{cy}{date}{sp}")
                            yield from self._yield_unique(f"{wc}_{cy}_{date}{sp}")
                            yield from self._yield_unique(f"{wc}_{date}_{cy}{sp}")

                # İsim + Ayraç + Tarih & Tarih + Ayraç + İsim & Zengin Özel Karakterler
                for date in self.dates:
                    for delim in DELIMITERS:
                        yield from self._yield_unique(f"{wc}{delim}{date}")
                        yield from self._yield_unique(f"{date}{delim}{wc}")

                    for sp in SPECIAL_CHARS:
                        yield from self._yield_unique(f"{wc}{date}{sp}")
                        yield from self._yield_unique(f"{wc}_{date}{sp}")
                        yield from self._yield_unique(f"{wc}.{date}{sp}")
                        yield from self._yield_unique(f"{sp}{wc}{date}")
                        yield from self._yield_unique(f"{sp}{wc}{date}{sp}")
                        yield from self._yield_unique(f"{date}{wc}{sp}")
                        yield from self._yield_unique(f"{date}_{wc}{sp}")

                # İsim + Konum / Plaka & Tarihler
                for loc in self.profile.locations:
                    for delim in ['', '_', '.', '-']:
                        yield from self._yield_unique(f"{wc}{delim}{loc}")
                        yield from self._yield_unique(f"{loc}{delim}{wc}")
                    for sp in TOP_SPECIALS:
                        yield from self._yield_unique(f"{wc}{loc}{sp}")
                        yield from self._yield_unique(f"{wc}_{loc}{sp}")
                    for date in self.dates:
                        yield from self._yield_unique(f"{wc}{loc}{date}")
                        yield from self._yield_unique(f"{wc}_{loc}_{date}")
                        for sp in TOP_SPECIALS:
                            yield from self._yield_unique(f"{wc}{loc}{date}{sp}")
                            yield from self._yield_unique(f"{wc}_{loc}_{date}{sp}")
                            yield from self._yield_unique(f"{wc}.{loc}.{date}{sp}")

        # 2. İlişki İkilileri (effective_relations: AliSevda, AsyaCivciv, Asya34 vb.)
        for p1, p2 in self.effective_relations:
            p1_cases = get_casing_variations(p1)
            p2_cases = get_casing_variations(p2)

            for c1 in p1_cases:
                for c2 in p2_cases:
                    for delim in ['', '_', '.', '-']:
                        yield from self._yield_unique(f"{c1}{delim}{c2}")

                    # c1 + c2 + Temel İnsan Ekleri & Ayraçlar (Cerendeniz_1, Cerendeniz1!, Denizceren34. vb.)
                    for h_suf in HUMAN_TOP_SUFFIXES:
                        yield from self._yield_unique(f"{c1}{c2}{h_suf}")
                        yield from self._yield_unique(f"{c1}_{c2}_{h_suf}")
                        yield from self._yield_unique(f"{c1}{c2}_{h_suf}")
                        yield from self._yield_unique(f"{c1}{c2}.{h_suf}")
                        if not any(c in h_suf for c in '!@#$%^&*()_+-=[]{}|;:,.<>?'):
                            for sp in TOP_SPECIALS:
                                yield from self._yield_unique(f"{c1}{c2}{h_suf}{sp}")
                                yield from self._yield_unique(f"{c1}_{c2}_{h_suf}{sp}")
                                yield from self._yield_unique(f"{c1}{c2}_{h_suf}{sp}")

                    # c1 + c2 + Tarih varyasyonları
                    for date in self.dates:
                        yield from self._yield_unique(f"{c1}{c2}{date}")
                        yield from self._yield_unique(f"{c1}_{c2}_{date}")
                        yield from self._yield_unique(f"{c1}.{c2}.{date}")
                        for sp in TOP_SPECIALS:
                            yield from self._yield_unique(f"{c1}{c2}{date}{sp}")
                            yield from self._yield_unique(f"{c1}_{c2}_{date}{sp}")
                            yield from self._yield_unique(f"{c1}.{c2}.{date}{sp}")
                            yield from self._yield_unique(f"{sp}{c1}_{c2}_{date}")

    def generate_tier_2_medium_priority(self) -> Generator[str, None, None]:
        """
        Tier 2: Orta olasılıklı adaylar (Genel son ekler, ilgi alanları, takımlar, prefix wraps, triples).
        Örn: Ali1234!, Sevda35!, fenerbahce1907!, Ali1907!, !Nurcan!
        """
        base_words = self.profile.names + self.profile.interests + self.profile.keywords

        for word in base_words:
            word_cases = get_casing_variations(word)
            for wc in word_cases:
                # Yaygın zengin son ekler ve özel karakter varyasyonları
                if settings.rules.include_common_suffixes:
                    for suffix in self.suffixes:
                        yield from self._yield_unique(f"{wc}{suffix}")
                        yield from self._yield_unique(f"{wc}_{suffix}")
                        yield from self._yield_unique(f"{wc}.{suffix}")
                        for sp in TOP_SPECIALS:
                            yield from self._yield_unique(f"{wc}{suffix}{sp}")
                            yield from self._yield_unique(f"{wc}_{suffix}{sp}")
                            yield from self._yield_unique(f"{sp}{wc}{suffix}")

                # Sarmalayıcılar (Prefix & Suffix wraps: !Ali!, _Ali_, !Ali123)
                for sp in ['!', '_', '.', '*', '#', '@']:
                    yield from self._yield_unique(f"{sp}{wc}{sp}")
                    for date in self.dates:
                        yield from self._yield_unique(f"{sp}{wc}{date}{sp}")
                        yield from self._yield_unique(f"{sp}{wc}_{date}{sp}")
                    for cy in self.active_club_years:
                        yield from self._yield_unique(f"{sp}{wc}{cy}{sp}")

                # İlgi alanları + Yıllar + Özel Karakterler
                for date in self.dates:
                    yield from self._yield_unique(f"{wc}{date}")
                    yield from self._yield_unique(f"{wc}_{date}")
                    for sp in TOP_SPECIALS:
                        yield from self._yield_unique(f"{wc}{date}{sp}")
                        yield from self._yield_unique(f"{wc}_{date}{sp}")

                    # İsim + Tarih + Ekler (örn: Nurcan2004123!, Nurcan_04_123)
                    for sfx in ['123', '1', '12', '!', '123!', '34', '06', '35', '01']:
                        yield from self._yield_unique(f"{wc}{date}{sfx}")
                        yield from self._yield_unique(f"{wc}_{date}_{sfx}")
                        yield from self._yield_unique(f"{wc}_{sfx}_{date}")
                        for sp in ['!', '.', '_', '*']:
                            yield from self._yield_unique(f"{wc}{date}{sfx}{sp}")
                            yield from self._yield_unique(f"{wc}_{date}_{sfx}{sp}")
                            yield from self._yield_unique(f"{wc}_{sfx}_{date}{sp}")
                            yield from self._yield_unique(f"{date}_{wc}_{sfx}{sp}")

        # İlişki + Suffixes & Specials
        for p1, p2 in self.effective_relations:
            c1 = p1.capitalize()
            c2 = p2.capitalize()
            for suffix in self.suffixes[:15]:
                yield from self._yield_unique(f"{c1}{c2}{suffix}")
                yield from self._yield_unique(f"{c1}_{c2}_{suffix}")
                for sp in ['!', '.', '_', '*']:
                    yield from self._yield_unique(f"{c1}{c2}{suffix}{sp}")
                    yield from self._yield_unique(f"{c1}_{c2}_{suffix}{sp}")

    def generate_tier_3_low_priority(self) -> Generator[str, None, None]:
        """
        Tier 3: Düşük olasılıklı adaylar (Leetspeak mutasyonları).
        Örn: @l1, @li2021!, 5evd@123!, Asy@2000!
        """
        if not settings.rules.include_leetspeak:
            return

        base_words = self.profile.names + self.profile.keywords + self.profile.interests[:2]

        for word in base_words:
            leet_variants = apply_leetspeak(word, max_variations=5)
            for lv in leet_variants:
                # Yalın Leetspeak (hem küçük hem capitalize)
                yield from self._yield_unique(lv)
                yield from self._yield_unique(lv.capitalize())

                # Leetspeak + Tarih varyasyonları & Özel karakterler
                for date in self.dates:
                    for delim in ['', '_', '.']:
                        yield from self._yield_unique(f"{lv}{delim}{date}")
                        yield from self._yield_unique(f"{lv.capitalize()}{delim}{date}")
                        for sp in TOP_SPECIALS:
                            yield from self._yield_unique(f"{lv}{delim}{date}{sp}")
                            yield from self._yield_unique(f"{lv.capitalize()}{delim}{date}{sp}")

                # Leetspeak + Kulüp Yılı
                for cy in self.active_club_years:
                    for sp in TOP_SPECIALS:
                        yield from self._yield_unique(f"{lv}{cy}{sp}")
                        yield from self._yield_unique(f"{lv.capitalize()}{cy}{sp}")

                # Leetspeak + Popüler Ekler & Specials
                for suffix in ['123', '1', '12', '1234', '2024', '2025', '34']:
                    yield from self._yield_unique(f"{lv}{suffix}")
                    for sp in TOP_SPECIALS:
                        yield from self._yield_unique(f"{lv}{suffix}{sp}")
                        yield from self._yield_unique(f"{lv.capitalize()}{suffix}{sp}")

        # Top ilişkiler için Leetspeak ikilileri (örn: nurc@n + w1nk1)
        for p1, p2 in self.effective_relations[:8]:
            l1_list = apply_leetspeak(p1, max_variations=2)
            l2_list = apply_leetspeak(p2, max_variations=2)
            for l1 in l1_list:
                for l2 in l2_list:
                    yield from self._yield_unique(f"{l1}{l2}")
                    for d in self.dates[:2]:
                        yield from self._yield_unique(f"{l1}{l2}{d}")
                        for sp in ['!', '.', '_']:
                            yield from self._yield_unique(f"{l1}{l2}{d}{sp}")

    def generate_all(self) -> Generator[str, None, None]:
        """
        Tüm katmanları sırayla akıtır (Tier 0 -> Tier 1 -> Tier 2 -> Tier 3).
        Böylece listenin başında daima en olası şifreler yer alır, RAM tüketimi sıfıra yakın kalır.
        """
        # Tier 0: Yapay Zeka & Semantik Sezgisel Kökler
        if self.semantic_roots:
            yield from self.generate_tier_0_ai_semantic()

        # Tier 1: En yüksek olasılık
        yield from self.generate_tier_1_high_priority()

        # Tier 2: Orta olasılık
        yield from self.generate_tier_2_medium_priority()

        # Tier 3: Leetspeak ve mutasyonlar
        yield from self.generate_tier_3_low_priority()
