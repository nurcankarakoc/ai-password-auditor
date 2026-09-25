"""
Cybzenor - AI Sağlayıcı Erişim Noktası
Proje artık tek bir AI sağlayıcısı kullanır: herhangi bir bulut/3. parti API anahtarı
gerektirmeyen LocalAIProvider (yerel küçük dil modeli -> deterministik kural motoru).
"""

from ai.base import BaseAIProvider
from ai.local_provider import local_ai_provider


def get_active_ai_provider() -> BaseAIProvider:
    """Süreç genelinde paylaşılan tek AI sağlayıcı örneğini döner."""
    return local_ai_provider
