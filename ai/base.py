"""
Cybzenor - Soyut AI Sağlayıcı Arayüzü
Farklı yapay zeka modelleri (Gemini, Local LLM, Mock vb.) için ortak kontrat.
"""

from abc import ABC, abstractmethod
from ai.schemas import TargetProfile


class BaseAIProvider(ABC):
    """Tüm AI entegrasyonlarının uymak zorunda olduğu soyut temel sınıf."""

    def __init__(self, api_key: str = None) -> None:
        self.api_key = api_key

    @abstractmethod
    def extract_target_profile(self, raw_text: str) -> TargetProfile:
        """
        Dağınık OSINT / hedef metnini analiz ederek yapılandırılmış
        TargetProfile nesnesine dönüştürür.
        
        :param raw_text: Sosyal medya biyografisi, özgeçmiş veya dağınık notlar
        :return: Doğrulanmış TargetProfile nesnesi
        """
        pass

    @abstractmethod
    def generate_semantic_password_roots(self, profile: TargetProfile) -> list[str]:
        """
        Hedef profilden anlamsal, tutarlı ve mantıklı kök parola kalıpları üretir.
        Örn: Beşiktaş için 'bjk', '1903', 'kartal' kökleri; isim ve hayvan ismi hibritleri.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Sağlayıcının kullanıma hazır (API anahtarı geçerli, kütüphane yüklü vb.)
        olup olmadığını bildirir.
        """
        pass

    @abstractmethod
    def infer_unknown_values(self, category: str, profile: TargetProfile) -> list[str]:
        """
        Kullanıcının VARLIĞINI bildiği ama TAM DEĞERİNİ bilmediği bir kategori için
        (örn. "evcil hayvanının adını bilmiyorum ama köpeği var") hedef profilin
        bağlamına göre en olası değerleri tahmin eder.

        :param category: Kategori anahtarı (örn. "pet", "child", "nickname", "color")
        :param profile: Bilinen diğer hedef bilgileri (isim/tarih/konum/ilgi alanı)
        :return: Tahmini değerler listesi (en olasıdan en az olasıya doğru sıralı değildir)
        """
        pass
