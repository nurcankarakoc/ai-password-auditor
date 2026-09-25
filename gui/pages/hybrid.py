"""Cybzenor GUI - Hibrit Wordlist Birleştirici sayfası."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from gui import backend, theme
from gui.pages.base import BasePage
from gui.pages.wordlist_viewer import open_wordlist_viewer
from gui.widgets import BackgroundTask, Card, LabeledEntry, LogConsole, PrimaryButton, SecondaryButton


class HybridPage(BasePage):
    TITLE = "Hibrit Wordlist Birleştirici"
    SUBTITLE = "İki veya daha fazla mevcut wordlist dosyasını tekilleştirerek tek bir listede birleştirin."

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._task = BackgroundTask(self)
        self._checkbox_vars: dict = {}
        self._build_source_card()
        self._build_options_card()

    def _build_source_card(self) -> None:
        self.source_card = Card(self.scroll, title="1. Kaynak Wordlist'leri Seçin",
                                 subtitle="Birleştirmek için en az 2 dosya işaretleyin.")
        self.source_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self.source_list = ctk.CTkFrame(self.source_card.body, fg_color="transparent")
        self.source_list.grid(row=0, column=0, sticky="ew")
        self.source_list.grid_columnconfigure(0, weight=1)

    def _render_sources(self) -> None:
        for w in self.source_list.winfo_children():
            w.destroy()
        self._checkbox_vars.clear()

        options = backend.list_all_wordlists()
        if len(options) < 2:
            ctk.CTkLabel(
                self.source_list, text="Birleştirmek için en az 2 wordlist gerekiyor. Önce bir liste üretin.",
                font=theme.font(12), text_color=theme.WARNING
            ).grid(row=0, column=0, sticky="w")
            return

        for i, path in enumerate(options):
            var = ctk.BooleanVar(value=False)
            count = backend.wordlist_line_count(path)
            label = "Varsayılan Liste" if path == backend.DEFAULT_WORDLIST else "Üretilmiş Liste"
            ctk.CTkCheckBox(
                self.source_list, text=f"{path.name}   ·   {label}   ·   {count:,} satır",
                variable=var, font=theme.font(12), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                border_color=theme.BORDER
            ).grid(row=i, column=0, sticky="w", pady=3)
            self._checkbox_vars[path] = var

    def _build_options_card(self) -> None:
        card = Card(self.scroll, title="2. Ayarlar ve Birleştir")
        card.grid(row=1, column=0, sticky="ew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.case_sensitive = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body, text="Büyük/küçük harf farkını koru (Örn: 'Admin' ile 'admin' ayrı tutulsun)",
            variable=self.case_sensitive, font=theme.font(12),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, border_color=theme.BORDER
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.e_filename = LabeledEntry(body, "Dosya Adı", "otomatik oluşturulur (ör. hybrid_liste1_liste2.txt)")
        self.e_filename.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew")
        self.run_btn = PrimaryButton(action_row, text="🧬 Birleştir", width=160, command=self._on_merge)
        self.run_btn.pack(side="left")
        self.view_btn = SecondaryButton(action_row, text="👁 Listeyi Görüntüle", width=170, command=self._open_last_result)
        self.progress = ctk.CTkProgressBar(action_row, mode="indeterminate", width=220, fg_color=theme.BG_SECONDARY, progress_color=theme.ACCENT)
        self.progress.pack(side="left", padx=16)
        self._last_output_path = None

        self.log = LogConsole(body, height=150)
        self.log.grid(row=3, column=0, sticky="ew", pady=(12, 0))

    def on_show(self) -> None:
        self._render_sources()

    def _open_last_result(self) -> None:
        if self._last_output_path is not None:
            open_wordlist_viewer(self.app, self._last_output_path)

    def _on_merge(self) -> None:
        chosen = [p for p, v in self._checkbox_vars.items() if v.get()]
        if len(chosen) < 2:
            messagebox.showwarning("Yetersiz Seçim", "Lütfen en az 2 wordlist dosyası işaretleyin.")
            return

        default_name = "hybrid_" + "_".join(p.stem for p in chosen)[:60]
        filename = self.e_filename.get() or default_name

        self.log.clear()
        self.view_btn.pack_forget()
        self.run_btn.configure(state="disabled", text="⏳ Birleştiriliyor...")
        self.progress.start()
        self.log.log(f"{len(chosen)} dosya birleştiriliyor...", "info")

        def work():
            return backend.merge_wordlists_hybrid(chosen, filename, self.case_sensitive.get())

        def on_done(meta):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🧬 Birleştir")
            self.log.log(f"✔ Hibrit liste oluşturuldu: {meta['output_file']}", "success")
            self.log.log(f"  Toplam kaynak satır : {meta['total_source_lines']:,}", "default")
            self.log.log(f"  Benzersiz kaydedilen: {meta['unique_written_lines']:,}", "default")
            self.log.log(f"  Elenen/mükerrer     : {meta['filtered_or_duplicate_lines']:,}", "default")
            self._last_output_path = backend.GENERATED_DIR / meta["output_file"]
            self.view_btn.pack(side="left")

        def on_error(err: Exception):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🧬 Birleştir")
            self.log.log(f"✖ Hata: {err}", "error")
            messagebox.showerror("Birleştirme Hatası", str(err))

        self._task.run(work, on_done, on_error)
