"""
Cybzenor - AI Sağlayıcı Orkestratörü
Birden fazla bulut AI sağlayıcısı (Gemini, OpenAI, Anthropic) arasında hangisinin
kullanılacağına karar verir. Gemini kalıcı bir ücretsiz katmana sahip olduğu için
öncelik sırası her zaman Gemini önce; OpenAI/Anthropic sadece Gemini düştüğünde
(kota/kesinti) devreye girer.
"""

from ai.base import BaseAIProvider
from ai.provider_gemini import GeminiAIProvider
from ai.provider_openai import OpenAIProvider
from ai.provider_anthropic import AnthropicProvider

CLOUD_PROVIDER_CLASSES = [GeminiAIProvider, OpenAIProvider, AnthropicProvider]


def get_active_ai_provider() -> BaseAIProvider:
    """
    Yapılandırılmış sağlayıcılar arasından (Gemini -> OpenAI -> Anthropic öncelik
    sırası) ilk KULLANILABİLİR olanı döner. Hiçbiri şu an aktif değilse, anahtarı
    olan ilkini döner (o da kendi zincirinde yerel modele/statik motora düşer).
    Hiç yapılandırılmış anahtar da yoksa Gemini nesnesini döner (varsayılan).
    """
    providers = [cls() for cls in CLOUD_PROVIDER_CLASSES]
    for provider in providers:
        if provider.is_available():
            return provider
    for provider in providers:
        if provider._keys:
            return provider
    return providers[0]


def any_cloud_ai_configured() -> bool:
    """En az bir sağlayıcıda kayıtlı anahtar var mı (onboarding ekranı için)."""
    return any(cls()._keys for cls in CLOUD_PROVIDER_CLASSES)
