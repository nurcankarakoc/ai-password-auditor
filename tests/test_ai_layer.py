"""
Cybzenor - Adım 3 AI Veri Katmanı Testleri
TargetProfile şeması, BaseAIProvider soyutlaması ve Fallback kural motoru testleri.
"""

import pytest
from ai.schemas import TargetProfile
from ai.base import BaseAIProvider
from ai.provider_gemini import GeminiAIProvider
from ai.provider_openai import OpenAIProvider
from ai.provider_anthropic import AnthropicProvider


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

    def test_gemini_provider_without_api_key_uses_fallback(self, monkeypatch):
        """API anahtarı verilmediğinde is_available False olmalı ve statik Fallback motoru çalışmalı."""
        # Bu makinede yerel AI modeli indirilmiş VE/VEYA .env'de gerçek bir Gemini anahtarı
        # kayıtlı olabilir; bu test özellikle deterministik statik kural motorunu doğruladığı
        # için ikisini de devre dışı bırakıyoruz.
        from ai.local_llm_engine import local_llm_engine
        monkeypatch.setattr(local_llm_engine, "is_available", lambda: False)
        monkeypatch.setattr("config.settings.settings.gemini_api_key", None)
        monkeypatch.setattr("config.settings.settings.gemini_api_keys", [])
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)

        provider = GeminiAIProvider(api_key=None)
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
        provider = GeminiAIProvider(api_key=None)
        profile = provider.extract_target_profile("")
        assert profile.is_empty() is True

    def test_cannot_instantiate_abstract_base_ai_provider(self):
        """Soyut BaseAIProvider sınıfının doğrudan somutlaştırılamayacağını doğrula."""
        with pytest.raises(TypeError):
            BaseAIProvider()


class TestMultiProviderSupport:
    """OpenAI/Anthropic sağlayıcıları, anahtar-format tespiti ve sağlayıcı seçim mantığı testleri."""

    def _disable_local_llm(self, monkeypatch):
        from ai.local_llm_engine import local_llm_engine
        monkeypatch.setattr(local_llm_engine, "is_available", lambda: False)

    def test_openai_provider_without_api_key_uses_fallback(self, monkeypatch):
        """OpenAI anahtarı yokken is_available False olmalı ve statik fallback çalışmalı."""
        self._disable_local_llm(monkeypatch)
        monkeypatch.setattr("config.settings.settings.openai_api_keys", [])
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEYS", raising=False)

        provider = OpenAIProvider(api_key=None)
        assert provider.is_available() is False
        assert provider.PROVIDER_LABEL == "OpenAI"

        profile = provider.extract_target_profile("İsim: Ahmet\nŞehir: Ankara\n")
        assert isinstance(profile, TargetProfile)
        assert "Ahmet" in profile.names

    def test_anthropic_provider_without_api_key_uses_fallback(self, monkeypatch):
        """Anthropic anahtarı yokken is_available False olmalı ve statik fallback çalışmalı."""
        self._disable_local_llm(monkeypatch)
        monkeypatch.setattr("config.settings.settings.anthropic_api_keys", [])
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEYS", raising=False)

        provider = AnthropicProvider(api_key=None)
        assert provider.is_available() is False
        assert provider.PROVIDER_LABEL == "Anthropic"

        profile = provider.extract_target_profile("İsim: Ahmet\nŞehir: Ankara\n")
        assert isinstance(profile, TargetProfile)
        assert "Ahmet" in profile.names

    def test_openai_and_anthropic_share_cascade_but_independent_down_state(self):
        """Farklı sağlayıcıların devre-kesici durumu birbirinden bağımsız olmalı (aynı anahtar farklı label)."""
        assert OpenAIProvider.PROVIDER_LABEL != AnthropicProvider.PROVIDER_LABEL != GeminiAIProvider.PROVIDER_LABEL

    def test_detect_provider_from_key(self):
        from config.settings import detect_provider_from_key
        assert detect_provider_from_key("sk-ant-api03-xxxxxxxxxxxxxxxxxxxx") == "anthropic"
        assert detect_provider_from_key("sk-proj-xxxxxxxxxxxxxxxxxxxx") == "openai"
        assert detect_provider_from_key("AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345") == "gemini"
        assert detect_provider_from_key("AQ.Ab8xxxxxxxxxxxxxxxxxxxxxHlEA") == "gemini"
        assert detect_provider_from_key("totally-unknown-format-12345") is None

    def test_save_ai_api_key_writes_correct_provider_field(self, tmp_path, monkeypatch):
        """save_ai_api_key doğru settings alanına ve .env değişkenine yazmalı, diğer sağlayıcıları etkilememeli."""
        import config.settings as settings_module

        fake_env = tmp_path / ".env"
        monkeypatch.setattr(settings_module, "ENV_FILE_PATH", fake_env)
        monkeypatch.setattr(settings_module.settings, "openai_api_keys", [])
        monkeypatch.setattr(settings_module.settings, "anthropic_api_keys", [])
        monkeypatch.setattr(settings_module.settings, "gemini_api_keys", [])
        monkeypatch.setattr(settings_module.settings, "gemini_api_key", None)

        result = settings_module.save_ai_api_key("sk-proj-fake-openai-key", "openai")
        assert result == ["sk-proj-fake-openai-key"]
        assert settings_module.settings.openai_api_keys == ["sk-proj-fake-openai-key"]
        assert settings_module.settings.anthropic_api_keys == []  # diğer sağlayıcı etkilenmemeli
        assert settings_module.settings.gemini_api_keys == []

        env_content = fake_env.read_text(encoding="utf-8")
        assert "OPENAI_API_KEYS=sk-proj-fake-openai-key" in env_content

    def test_get_active_ai_provider_falls_back_through_priority_order(self, monkeypatch):
        """Gemini kullanılamazken yapılandırılmış OpenAI'ye, o da yoksa Anthropic'e düşmeli."""
        from ai import ai_manager

        monkeypatch.setattr("config.settings.settings.gemini_api_keys", [])
        monkeypatch.setattr("config.settings.settings.gemini_api_key", None)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        monkeypatch.setattr("config.settings.settings.openai_api_keys", [])
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
        monkeypatch.setattr("config.settings.settings.anthropic_api_keys", ["sk-ant-fake-key"])
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEYS", raising=False)

        # Gemini/OpenAI'de hiç anahtar yok (is_available False); anahtarı OLAN tek
        # sağlayıcı Anthropic olduğu için seçilmesi gereken de o.
        provider = ai_manager.get_active_ai_provider()
        assert provider.PROVIDER_LABEL == "Anthropic"

    def test_get_active_ai_provider_defaults_to_gemini_when_nothing_configured(self, monkeypatch):
        """Hiç anahtar yapılandırılmamışsa varsayılan olarak Gemini nesnesi dönmeli."""
        from ai import ai_manager

        monkeypatch.setattr("config.settings.settings.gemini_api_keys", [])
        monkeypatch.setattr("config.settings.settings.gemini_api_key", None)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        monkeypatch.setattr("config.settings.settings.openai_api_keys", [])
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
        monkeypatch.setattr("config.settings.settings.anthropic_api_keys", [])
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEYS", raising=False)

        provider = ai_manager.get_active_ai_provider()
        assert provider.PROVIDER_LABEL == "Gemini"
