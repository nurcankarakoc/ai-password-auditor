"""Cybzenor GUI - Sayfa Temel Sınıfı (ortak başlık + kaydırılabilir gövde)."""

from __future__ import annotations

import customtkinter as ctk

from gui import theme


class BasePage(ctk.CTkFrame):
    """
    Tüm sayfaların miras aldığı ortak iskelet: üstte başlık/açıklama, altında
    dikey kaydırılabilir bir içerik alanı (`self.scroll`).
    """

    TITLE = ""
    SUBTITLE = ""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color=theme.BG_PRIMARY)
        self.app = app
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 10))
        ctk.CTkLabel(header, text=self.TITLE, font=theme.font(24, "bold"), text_color=theme.TEXT_PRIMARY) \
            .pack(anchor="w")
        if self.SUBTITLE:
            ctk.CTkLabel(header, text=self.SUBTITLE, font=theme.font(13), text_color=theme.TEXT_SECONDARY) \
                .pack(anchor="w", pady=(4, 0))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 24))
        self.scroll.grid_columnconfigure(0, weight=1)

    def on_show(self) -> None:  # alt sınıflar isterse override eder
        pass
