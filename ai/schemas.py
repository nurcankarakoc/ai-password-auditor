"""
Cybzenor - Hedef Profil Veri Modelleri
OSINT ve profil girdilerini yapılandırılmış veri şemasına (NER) dönüştürmek için Pydantic modelleri.
"""

from typing import List
from pydantic import BaseModel, Field, field_validator


class TargetProfile(BaseModel):
    """
    Hedefe ait dağınık metinlerden (OSINT) çıkarılan yapılandırılmış profil nesnesi.
    """
    names: List[str] = Field(
        default_factory=list,
        description="Hedef kişi, eşi, çocukları, evcil hayvanı vb. isimler"
    )
    dates: List[str] = Field(
        default_factory=list,
        description="Doğum yılları, evlilik tarihi, kuruluş yılları (örn: '1990', '2015', '1907')"
    )
    locations: List[str] = Field(
        default_factory=list,
        description="Doğum yeri, yaşanılan şehir, memleket veya plaka kodları (örn: 'Istanbul', '34')"
    )
    interests: List[str] = Field(
        default_factory=list,
        description="Tuttuğu takım, hobiler, müzik grupları vb. (örn: 'fenerbahce', 'gitar')"
    )
    relations: List[List[str]] = Field(
        default_factory=list,
        description="Birlikte kullanılan ilişki ikilileri (örn: [['Ali', 'Sevda'], ['Burak', 'Cansu']])"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Hedefe özel ek anahtar kelimeler, lakaplar veya şirket adları"
    )

    @field_validator("names", "dates", "locations", "interests", "keywords", mode="before")
    @classmethod
    def clean_string_list(cls, v):
        """Boşlukları temizle ve boş stringleri filtrele."""
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("relations", mode="before")
    @classmethod
    def clean_relations_list(cls, v):
        """İlişki listesindeki elemanları temizle."""
        if isinstance(v, list):
            cleaned = []
            for pair in v:
                if isinstance(pair, (list, tuple)):
                    cleaned_pair = [str(item).strip() for item in pair if str(item).strip()]
                    if cleaned_pair:
                        cleaned.append(cleaned_pair)
            return cleaned
        return v

    def is_empty(self) -> bool:
        """Profilin tamamen boş olup olmadığını denetler."""
        return not any([
            self.names,
            self.dates,
            self.locations,
            self.interests,
            self.relations,
            self.keywords
        ])

    def to_summary_dict(self) -> dict:
        """CLI veya loglarda gösterilmek üzere özet döner."""
        return {
            "İsimler": len(self.names),
            "Tarihler": len(self.dates),
            "Konumlar": len(self.locations),
            "İlgi Alanları": len(self.interests),
            "İlişkiler": len(self.relations),
            "Anahtar Kelimeler": len(self.keywords)
        }

    def to_detailed_dict(self) -> dict:
        """Hedef profilin tüm detaylarını JSON uyumlu sözlük olarak döner."""
        return {
            "names": self.names,
            "dates": self.dates,
            "locations": self.locations,
            "interests": self.interests,
            "relations": self.relations,
            "keywords": self.keywords
        }


class PasswordPolicy(BaseModel):
    """
    Hedef sistemin parola güvenlik kurallarını temsil eden model.
    Yalnızca bu kurallara uyan adaylar listeye dahil edilir.
    """
    min_length: int = Field(default=6, ge=1, le=128, description="Minimum karakter sınırı")
    max_length: int = Field(default=32, ge=1, le=256, description="Maksimum karakter sınırı")
    require_uppercase: bool = Field(default=False, description="En az bir büyük harf (A-Z) zorunlu mu?")
    require_lowercase: bool = Field(default=False, description="En az bir küçük harf (a-z) zorunlu mu?")
    require_digit: bool = Field(default=False, description="En az bir rakam (0-9) zorunlu mu?")
    require_special: bool = Field(default=False, description="En az bir özel karakter (!, @, _, . vb.) zorunlu mu?")
    special_chars: str = Field(default="!@#$%^&*()_+-=[]{}|;:,.<>?", description="Kabul edilen özel karakterler")

    def is_satisfied(self, candidate: str) -> bool:
        """Aday parolanın güvenlik politikasına uyup uymadığını denetler."""
        if not (self.min_length <= len(candidate) <= self.max_length):
            return False
        if self.require_uppercase and not any(c.isupper() for c in candidate):
            return False
        if self.require_lowercase and not any(c.islower() for c in candidate):
            return False
        if self.require_digit and not any(c.isdigit() for c in candidate):
            return False
        if self.require_special and not any(c in self.special_chars for c in candidate):
            return False
        return True

    def summary(self) -> str:
        rules = [f"Uzunluk: {self.min_length}-{self.max_length}"]
        if self.require_uppercase:
            rules.append("Büyük Harf")
        if self.require_lowercase:
            rules.append("Küçük Harf")
        if self.require_digit:
            rules.append("Rakam")
        if self.require_special:
            rules.append("Özel Karakter")
        return ", ".join(rules)
