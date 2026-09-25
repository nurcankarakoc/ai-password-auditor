"""
Cybzenor GUI - Görsel Tema Sabitleri
Tüm sayfaların ortak kullandığı renk paleti, font ve boyut sabitleri tek yerden yönetilir.
"""

import customtkinter as ctk

# Marka rengi: siber/güvenlik temalı koyu lacivert + neon yeşil vurgu.
BG_PRIMARY = "#0f1117"
BG_SECONDARY = "#161925"
BG_CARD = "#1c2030"
BG_CARD_HOVER = "#232838"
BORDER = "#2a2f42"

ACCENT = "#00d68f"          # Neon yeşil (başarı / marka rengi)
ACCENT_HOVER = "#00b87a"
ACCENT_SOFT = "#0f3a2c"

DANGER = "#ff5c66"
DANGER_HOVER = "#e64a54"
WARNING = "#ffb84d"
INFO = "#4fa8ff"

TEXT_PRIMARY = "#f2f4f8"
TEXT_SECONDARY = "#9aa1b4"
TEXT_MUTED = "#6b7186"

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def font_mono(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_MONO, size=size, weight=weight)


def apply_appearance() -> None:
    """Uygulama genelinde koyu tema ve marka rengini uygular."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
