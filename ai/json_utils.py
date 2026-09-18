"""
Cybzenor - Paylaşımlı JSON Ayrıştırma Yardımcıları
Bulut AI sağlayıcılarının (ve yerel dil modelinin) serbest metin yanıtlarından
JSON çıkarması için ortak regex tabanlı ayrıştırıcı.
"""

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """
    Metin içindeki ilk JSON yapısını (liste veya nesne) döndürür. Model, talimatlara
    rağmen JSON'un etrafına açıklama ekleyebiliyor; bu regex ile o gürültü elenir.
    Geçerli bir JSON bulunamazsa ValueError fırlatılır.
    """
    match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
    if not match:
        raise ValueError(f"Yanıtta JSON bulunamadı: {text[:200]}")
    return json.loads(match.group(1))
