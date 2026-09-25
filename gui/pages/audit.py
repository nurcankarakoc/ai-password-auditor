"""Cybzenor GUI - Yerel Hash Denetim Motoru sayfası."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from gui import backend, theme
from gui.pages.base import BasePage
from gui.widgets import BackgroundTask, Card, LabeledEntry, LogConsole, PrimaryButton


class AuditPage(BasePage):
    TITLE = "Yerel Hash Denetim Motoru"
    SUBTITLE = "Bir wordlist'in hedef SHA-256 hash'ini yakalayıp yakalayamayacağını saniyeler içinde test edin."

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._task = BackgroundTask(self)
        self._target_records: list[backend.TargetRecord] = []
        self._build_target_card()
        self._build_wordlist_card()
        self._build_result_card()

    # ------------------------------------------------------------------ Hedef seçimi
    def _build_target_card(self) -> None:
        card = Card(self.scroll, title="1. Hedef Hash / Parola",
                    subtitle="Kayıtlı bir hedef profilinden seçin veya manuel bir SHA-256 hash / açık parola girin.")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.target_combo = ctk.CTkComboBox(
            body, values=["(Kayıtlı hedef yok)"], font=theme.font(13), dropdown_font=theme.font(13),
            fg_color=theme.BG_SECONDARY, border_color=theme.BORDER, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER, command=self._on_target_select
        )
        self.target_combo.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.e_manual = LabeledEntry(body, "veya Manuel SHA-256 Hash / Açık Parola Gir", "Örn: Pamuk2021! veya 64 haneli hash")
        self.e_manual.grid(row=1, column=0, sticky="ew")

    def _on_target_select(self, choice: str) -> None:
        idx = self.target_combo.cget("values").index(choice) if choice in self.target_combo.cget("values") else -1
        if 0 <= idx < len(self._target_records):
            rec = self._target_records[idx]
            if rec.has_hash:
                self.e_manual.set("")

    def _resolve_target(self) -> tuple[str, str] | None:
        manual = self.e_manual.get()
        if manual:
            target_hash = backend.resolve_hash_input(manual)
            return target_hash, f"Manuel ({manual[:24]}{'…' if len(manual) > 24 else ''})"

        choice = self.target_combo.get()
        values = self.target_combo.cget("values")
        if choice in values and self._target_records:
            idx = values.index(choice)
            if idx < len(self._target_records):
                rec = self._target_records[idx]
                if not rec.has_hash:
                    messagebox.showerror("Test Parolası Yok", f"'{rec.target_name}' hedefinin kayıtlı bir test parolası/hash'i yok.")
                    return None
                return rec.target_hash, f"{rec.target_name} ({rec.plain_password_hint})"

        messagebox.showwarning("Hedef Seçilmedi", "Lütfen kayıtlı bir hedef seçin veya manuel bir hash/parola girin.")
        return None

    # ------------------------------------------------------------------ Wordlist seçimi
    def _build_wordlist_card(self) -> None:
        card = Card(self.scroll, title="2. Wordlist Seç")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.wordlist_combo = ctk.CTkComboBox(
            body, values=["(Wordlist yok)"], font=theme.font(13), dropdown_font=theme.font(13),
            fg_color=theme.BG_SECONDARY, border_color=theme.BORDER, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
        )
        self.wordlist_combo.grid(row=0, column=0, sticky="ew")
        self._wordlist_paths: list = []

        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.run_btn = PrimaryButton(action_row, text="🔍 Denetimi Başlat", width=180, command=self._on_audit)
        self.run_btn.pack(side="left")
        self.progress = ctk.CTkProgressBar(action_row, mode="indeterminate", width=220, fg_color=theme.BG_SECONDARY, progress_color=theme.ACCENT)
        self.progress.pack(side="left", padx=16)

    # ------------------------------------------------------------------ Sonuç
    def _build_result_card(self) -> None:
        card = Card(self.scroll, title="Sonuç")
        card.grid(row=2, column=0, sticky="ew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.result_label = ctk.CTkLabel(body, text="Henüz denetim yapılmadı.", font=theme.font(14, "bold"), text_color=theme.TEXT_SECONDARY, anchor="w")
        self.result_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.log = LogConsole(body, height=160)
        self.log.grid(row=1, column=0, sticky="ew")

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._target_records = backend.list_target_records()
        target_values = [f"{r.target_name}" + ("" if r.has_hash else "  (hash yok)") for r in self._target_records] \
            or ["(Kayıtlı hedef yok)"]
        self.target_combo.configure(values=target_values)
        self.target_combo.set(target_values[0])

        self._wordlist_paths = backend.list_all_wordlists()
        wl_values = [p.name + ("  (Varsayılan)" if p == backend.DEFAULT_WORDLIST else "") for p in self._wordlist_paths] \
            or ["(Wordlist yok)"]
        self.wordlist_combo.configure(values=wl_values)
        self.wordlist_combo.set(wl_values[0])

    def _on_audit(self) -> None:
        target = self._resolve_target()
        if target is None:
            return
        target_hash, target_label = target

        if not self._wordlist_paths:
            messagebox.showwarning("Wordlist Yok", "Önce bir wordlist üretin.")
            return
        wl_idx = self.wordlist_combo.cget("values").index(self.wordlist_combo.get())
        wordlist_path = self._wordlist_paths[wl_idx]

        self.log.clear()
        self.result_label.configure(text="Denetim çalışıyor...", text_color=theme.TEXT_SECONDARY)
        self.run_btn.configure(state="disabled", text="⏳ Çalışıyor...")
        self.progress.start()
        self.log.log(f"Hedef : {target_label}", "info")
        self.log.log(f"Liste : {wordlist_path.name}", "info")

        def work():
            return backend.run_hash_audit(target_hash, wordlist_path)

        def on_done(result):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🔍 Denetimi Başlat")
            if result.matched:
                self.result_label.configure(text=f"✔ PAROLA BULUNDU: {result.matched_password}", text_color=theme.ACCENT)
                self.log.log(f"✔ Eşleşme! Parola: {result.matched_password}", "success")
                self.log.log(f"  Bulunduğu sıra : {result.position:,}. deneme", "default")
            else:
                self.result_label.configure(text="✖ Eşleşme bulunamadı", text_color=theme.DANGER)
                self.log.log("✖ Eşleşme bulunamadı.", "error")
            self.log.log(f"  Test edilen aday : {result.total_tested:,}", "default")
            self.log.log(f"  Geçen süre       : {result.duration_seconds} sn", "default")
            self.log.log(f"  Ortalama hız     : {result.hashes_per_second:,.0f} hash/sn", "default")

        def on_error(err: Exception):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🔍 Denetimi Başlat")
            self.result_label.configure(text="✖ Hata oluştu", text_color=theme.DANGER)
            self.log.log(f"✖ Hata: {err}", "error")
            messagebox.showerror("Denetim Hatası", str(err))

        self._task.run(work, on_done, on_error)
