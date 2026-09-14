"""
Smart Password Auditor (SPA) - Adım 4 Candidate Generator Testleri
Generator akışı, Leetspeak, Türkçe karakter normalizasyonu ve aşamalı üretim (Tiered) testleri.
"""

import inspect
import pytest
from ai.schemas import TargetProfile
from core.candidate_generator import (
    CandidateGenerator,
    apply_leetspeak,
    normalize_turkish,
    get_casing_variations,
    expand_date_variations,
)


@pytest.fixture
def sample_profile() -> TargetProfile:
    """Test için örnek hedef profili."""
    return TargetProfile(
        names=["Ali", "Sevda"],
        dates=["2021", "1995"],
        locations=["Istanbul", "34"],
        interests=["fenerbahce"],
        relations=[["Ali", "Sevda"]],
        keywords=["kartal"]
    )


class TestGeneratorUtilityFunctions:
    """Yardımcı dönüşüm fonksiyonlarının testleri."""

    def test_turkish_normalization(self):
        """Türkçe karakterlerin ASCII karşılıklarına dönüştüğünü doğrula."""
        assert normalize_turkish("Şükrü") == "Sukru"
        assert normalize_turkish("Çağla") == "Cagla"
        assert normalize_turkish("Ömer") == "Omer"

    def test_casing_variations(self):
        """Küçük, BÜYÜK ve Capitalize varyasyonlarının üretildiğini doğrula."""
        vars_ = get_casing_variations("ali")
        assert "ali" in vars_
        assert "Ali" in vars_
        assert "ALI" in vars_

    def test_leetspeak_mutation(self):
        """Leetspeak kurallarının (a->@/4, e->3, i->1/!, s->5/$) uygulandığını doğrula."""
        variants = apply_leetspeak("sevda")
        # 's' -> '5' veya '$', 'e' -> '3', 'a' -> '@' veya '4'
        assert any("5" in v or "$" in v or "3" in v or "@" in v or "4" in v for v in variants)


class TestCandidateGeneratorEngine:
    """CandidateGenerator sınıfının motor ve akış testleri."""

    def test_generator_returns_generator_not_list(self, sample_profile: TargetProfile):
        """Metotların list yerine generator (yield) döndürdüğünü doğrula (RAM Dostu)."""
        gen = CandidateGenerator(sample_profile)
        tier1_gen = gen.generate_tier_1_high_priority()
        all_gen = gen.generate_all()

        assert inspect.isgenerator(tier1_gen)
        assert inspect.isgenerator(all_gen)

    def test_tier_1_contains_high_probability_candidates(self, sample_profile: TargetProfile):
        """Tier 1 içinde doğrudan isim + yıl ve ilişki kombinasyonlarının bulunduğunu doğrula."""
        gen = CandidateGenerator(sample_profile)
        tier1_list = list(gen.generate_tier_1_high_priority())

        # İsim + Tarih
        assert "Ali2021" in tier1_list or "ali2021" in tier1_list
        assert "Ali_2021" in tier1_list
        # İlişki kombinasyonları
        assert any("AliSevda" in c or "SevdaAli" in c for c in tier1_list)
        assert any("AliSevda2021" in c for c in tier1_list)

    def test_tier_2_contains_common_suffixes(self, sample_profile: TargetProfile):
        """Tier 2 içinde yaygın son eklerin (123, !, 1907 vb.) yer aldığını doğrula."""
        gen = CandidateGenerator(sample_profile)
        tier2_list = list(gen.generate_tier_2_medium_priority())

        assert any(c.endswith("123") for c in tier2_list)
        assert any(c.endswith("!") for c in tier2_list)

    def test_tier_3_contains_leetspeak(self, sample_profile: TargetProfile):
        """Tier 3 içinde leetspeak mutasyonlarının bulunduğunu doğrula."""
        gen = CandidateGenerator(sample_profile)
        tier3_list = list(gen.generate_tier_3_low_priority())

        # Ali veya Sevda leetspeak halleri
        assert any("@" in c or "1" in c or "3" in c or "5" in c for c in tier3_list)

    def test_generate_all_preserves_tiered_order(self, sample_profile: TargetProfile):
        """generate_all çağrıldığında Tier 1'in Tier 3'ten önce geldiğini doğrula."""
        gen = CandidateGenerator(sample_profile)
        all_candidates = list(gen.generate_all())

        assert len(all_candidates) > 50
        # İlk 30 aday içinde leetspeak (Tier 3) değil, doğal isim/tarih kombinasyonları (Tier 1) olmalı
        first_20 = all_candidates[:20]
        assert any("Ali" in c or "Sevda" in c for c in first_20)

    def test_length_limits_strictly_respected(self, sample_profile: TargetProfile):
        """Üretilen tüm adayların min_length (6) ve max_length (32) sınırında olduğunu doğrula."""
        from config.settings import settings
        gen = CandidateGenerator(sample_profile)

        for candidate in gen.generate_all():
            assert settings.wordlist.min_length <= len(candidate) <= settings.wordlist.max_length

    def test_date_expansion_parsing(self):
        """Tarih varyasyonlarının (tekil yıl ve tam tarih) doğru ayrıştırıldığını doğrula."""
        vars_year = expand_date_variations(["2004"])
        assert "2004" in vars_year
        assert "04" in vars_year
        assert "0404" in vars_year

        vars_full = expand_date_variations(["10.10.2004"])
        assert "2004" in vars_full
        assert "04" in vars_full
        assert "1010" in vars_full
        assert "10102004" in vars_full

    def test_cross_relations_between_all_names(self):
        """Profilde açık ilişki tanımlanmasa dahi tüm isimlerin çaprazlandığını doğrula."""
        p = TargetProfile(
            names=["Nurcan", "Winki", "Altun"],
            dates=["2004"],
            locations=[],
            interests=[],
            relations=[],
            keywords=[]
        )
        gen = CandidateGenerator(p)
        cands = list(gen.generate_all())

        # Nurcan & Winki, Nurcan & Altun çaprazları bulunmalı
        assert any("NurcanWinki" in c or "WinkiNurcan" in c for c in cands)
        assert any("NurcanAltun" in c or "AltunNurcan" in c for c in cands)

    def test_high_volume_generation_realistic_counts(self):
        """Zengin bir profilde 1500+ parola adayı üretildiğini doğrula."""
        p = TargetProfile(
            names=["Nurcan", "Winki", "Altun", "Sener"],
            dates=["2004"],
            locations=["34"],
            interests=["besiktas"],
            relations=[],
            keywords=["mor"]
        )
        gen = CandidateGenerator(p)
        cands = list(gen.generate_all())

        # En az 1500 - 3000+ zengin aday üretilmeli
        assert len(cands) >= 1500

    def test_password_policy_strict_filtering(self):
        """Parola politikası (min 8 hane, özel karakter zorunlu) verildiğinde tüm adayların uyduğunu doğrula."""
        from ai.schemas import PasswordPolicy
        p = TargetProfile(
            names=["Nurcan"],
            dates=["2004"],
            locations=[],
            interests=[],
            relations=[],
            keywords=[]
        )
        policy = PasswordPolicy(min_length=8, require_special=True, require_uppercase=True)
        gen = CandidateGenerator(p, policy=policy)
        cands = list(gen.generate_all())

        assert len(cands) > 0
        for cand in cands:
            assert len(cand) >= 8
            assert any(c.isupper() for c in cand)
            assert any(c in policy.special_chars for c in cand)

    def test_anti_noise_no_duplicate_dates(self):
        """20042004 veya 2004_2004 gibi anlamsız çifte yıl tekrarlarının elendiğini doğrula."""
        p = TargetProfile(
            names=["Krakoç"],
            dates=["2004"],
            locations=[],
            interests=[],
            relations=[],
            keywords=[]
        )
        gen = CandidateGenerator(p)
        cands = list(gen.generate_all())

        assert not any("20042004" in c for c in cands)
        assert not any("2004_2004" in c for c in cands)
        assert not any("2004.2004" in c for c in cands)

    def test_club_conflict_resolution(self):
        """Hedef Fenerbahçeli olduğunda rakip takım yıllarının (1903, 1905) üretilmediğini doğrula."""
        p = TargetProfile(
            names=["Krakoç"],
            dates=["2004"],
            locations=["34"],
            interests=["fenerbahçe"],
            relations=[],
            keywords=[]
        )
        gen = CandidateGenerator(p)
        cands = list(gen.generate_all())

        # 1907 bulunmalı
        assert any("1907" in c for c in cands)
        # 1903 ve 1905 kesinlikle bulunmamalı
        assert not any("1903" in c for c in cands)
        assert not any("1905" in c for c in cands)

    def test_human_basic_patterns_generated(self):
        """İnsanların en çok kullandığı Nurcan123, Nurcan1, Nurcan! gibi temel kalıpların üretildiğini doğrula."""
        p = TargetProfile(
            names=["Nurcan"],
            dates=["2004"],
            locations=[],
            interests=[],
            relations=[],
            keywords=[]
        )
        gen = CandidateGenerator(p)
        tier1 = list(gen.generate_tier_1_high_priority())

        # Nurcan123, Nurcan1, Nurcan! Tier 1 içinde yer almalı
        assert "Nurcan123" in tier1
        assert "Nurcan1" in tier1
        assert "Nurcan!" in tier1
        assert "Nurcan123!" in tier1

