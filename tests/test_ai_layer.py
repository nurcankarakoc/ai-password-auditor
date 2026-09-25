"""
Cybzenor - Adım 3 AI Veri Katmanı Testleri
TargetProfile şeması, BaseAIProvider soyutlaması ve Fallback kural motoru testleri.
"""

import pytest
from ai.schemas import TargetProfile
from ai.base import BaseAIProvider
from ai.local_provider import LocalAIProvider


class TestTargetProfileSchema:
    """TargetProfile Pydantic veri modeli testleri."""

    def test_target_profile_defaults(self):
        """Varsayılan alanların boş liste olarak başlatıldığını doğrula."""
        profile = TargetProfile()
        assert profile.names == []
        assert profile.dates == []
        assert profile.locations == []
        assert profile.interests == []
        assert profile.relations == []
        assert profile.keywords == []
        assert profile.is_empty() is True

    def test_target_profile_with_valid_data(self):
        """Veri içeren profilin doğrulanıp temizlendiğini test et."""
        profile = TargetProfile(
            names=[" Ali ", "Sevda"],
            dates=["1990", " 2021 "],
            locations=["Istanbul", "34"],
            interests=["fenerbahce"],
            relations=[["Ali", "Sevda"]],
            keywords=["developer"]
        )
        assert profile.is_empty() is False
        assert profile.names == ["Ali", "Sevda"]
        assert profile.dates == ["1990", "2021"]
        assert profile.locations == ["Istanbul", "34"]
        assert profile.relations == [["Ali", "Sevda"]]

    def test_target_profile_summary(self):
        """to_summary_dict fonksiyonunun alan sayılarını doğru verdiğini test et."""
        profile = TargetProfile(names=["Ahmet"], dates=["1995"])
        summary = profile.to_summary_dict()
        assert summary["İsimler"] == 1
        assert summary["Tarihler"] == 1
        assert summary["Konumlar"] == 0


class TestAIProviderAbstractionAndFallback:
    """AI sağlayıcı soyutlaması ve deterministik fallback motoru testleri."""

    def test_local_provider_without_model_uses_fallback(self, monkeypatch):
        """Yerel dil modeli kurulu değilken is_available False olmalı ve statik Fallback motoru çalışmalı."""
        from ai.local_llm_engine import local_llm_engine
        monkeypatch.setattr(local_llm_engine, "is_available", lambda: False)

        provider = LocalAIProvider()
        assert provider.is_available() is False

        raw_osint = (
            "Hedef Bilgileri:\n"
            "İsim: Ahmet, Merve\n"
            "Doğum Yılı: 1993\n"
            "Şehir: Ankara\n"
            "Takım: fenerbahce\n"
        )
        profile = provider.extract_target_profile(raw_osint)

        assert isinstance(profile, TargetProfile)
        assert "Ahmet" in profile.names
        assert "Merve" in profile.names
        assert "1993" in profile.dates
        assert "Ankara" in profile.locations
        assert "06" in profile.locations  # Ankara'nın plaka kodu otomatik eklenmeli
        assert "fenerbahce" in profile.interests
        assert len(profile.relations) >= 1

    def test_fallback_empty_input(self):
        """Boş metin verildiğinde boş profil dönmeli."""
        provider = LocalAIProvider()
        profile = provider.extract_target_profile("")
        assert profile.is_empty() is True

    def test_cannot_instantiate_abstract_base_ai_provider(self):
        """Soyut BaseAIProvider sınıfının doğrudan somutlaştırılamayacağını doğrula."""
        with pytest.raises(TypeError):
            BaseAIProvider()

    def test_get_active_ai_provider_returns_local_provider(self):
        """ai_manager, tek ve daima aynı yerel AI sağlayıcı örneğini dönmeli (bulut sağlayıcı yok)."""
        from ai import ai_manager
        provider = ai_manager.get_active_ai_provider()
        assert isinstance(provider, LocalAIProvider)
        assert provider is ai_manager.get_active_ai_provider()
