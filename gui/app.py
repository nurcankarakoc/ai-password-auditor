"""
Cybzenor GUI - Ana Uygulama Penceresi
Sol tarafta sekme navigasyonu, sağ tarafta içerik alanı olan tek pencereli masaüstü kabuk.
Her sayfa `gui/pages/` altında ayrı bir modülde tanımlıdır ve yalnızca ekrana geldiğinde
(`on_show`) diskten güncel veriyi okur; bu sayede sayfalar arası state senkronizasyonu
gerekmez.
"""

from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

# Proje kökünü sys.path'e ekle (bu dosya doğrudan `python gui/app.py` ile de çalıştırılabilsin diye)
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from gui import theme  # noqa: E402
from gui.pages.dashboard import DashboardPage  # noqa: E402
from gui.pages.generate import GeneratePage  # noqa: E402
from gui.pages.hybrid import HybridPage  # noqa: E402
from gui.pages.audit import AuditPage  # noqa: E402
from gui.pages.online import OnlinePage  # noqa: E402
from gui.pages.settings_page import SettingsPage  # noqa: E402

NAV_ITEMS = [
    ("dashboard", "🎯", "Hedefler & Genel Bakış"),
    ("generate", "🧠", "AI Hedefli Liste Üretimi"),
    ("hybrid", "🧬", "Hibrit Liste Birleştirici"),
    ("audit", "🔍", "Yerel Hash Denetimi"),
    ("online", "🌐", "Canlı Login Denetimi"),
    ("settings", "⚙️", "Ayarlar"),
]


class CybzenorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Cybzenor - Akıllı Hedefli Parola Denetim Aracı")
        self.geometry("1220x760")
        self.minsize(1040, 640)
        self.configure(fg_color=theme.BG_PRIMARY)

        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()

        self.pages: dict[str, ctk.CTkFrame] = {}
        self._register_pages()
        self.show_page("dashboard")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ Sidebar
    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=theme.BG_SECONDARY)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(len(NAV_ITEMS) + 2, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 4))
        ctk.CTkLabel(
            brand, text="🛡️ CYBZENOR", font=theme.font(20, "bold"), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand, text="Parola Denetim Framework'ü", font=theme.font(11), text_color=theme.TEXT_MUTED
        ).pack(anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color=theme.BORDER).grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 10))

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, (key, icon, label) in enumerate(NAV_ITEMS, start=2):
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}   {label}", anchor="w",
                fg_color="transparent", hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_SECONDARY, font=theme.font(13),
                corner_radius=8, height=42,
                command=lambda k=key: self.show_page(k),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            self._nav_buttons[key] = btn

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=len(NAV_ITEMS) + 3, column=0, sticky="ews", padx=20, pady=16)
        ctk.CTkLabel(
            footer, text="⚠️ Yalnızca yetkili hedeflerde kullanın.",
            font=theme.font(10), text_color=theme.TEXT_MUTED, wraplength=200, justify="left"
        ).pack(anchor="w")

    def _highlight_nav(self, active_key: str) -> None:
        for key, btn in self._nav_buttons.items():
            if key == active_key:
                btn.configure(fg_color=theme.ACCENT_SOFT, text_color=theme.ACCENT, font=theme.font(13, "bold"))
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT_SECONDARY, font=theme.font(13))

    # ------------------------------------------------------------------ Content
    def _build_content_area(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=theme.BG_PRIMARY, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def _register_pages(self) -> None:
        page_classes = {
            "dashboard": DashboardPage,
            "generate": GeneratePage,
            "hybrid": HybridPage,
            "audit": AuditPage,
            "online": OnlinePage,
            "settings": SettingsPage,
        }
        for key, cls in page_classes.items():
            page = cls(self.content, app=self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

    def show_page(self, key: str) -> None:
        page = self.pages[key]
        page.tkraise()
        self._highlight_nav(key)
        if hasattr(page, "on_show"):
            try:
                page.on_show()
            except Exception:
                pass

    def _on_close(self) -> None:
        self.destroy()


def main() -> None:
    theme.apply_appearance()
    app = CybzenorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
