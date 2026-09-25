"""
Cybzenor GUI - Wordlist Görüntüleyici
Üretilmiş/varsayılan bir wordlist dosyasının içeriğini, tamamını belleğe yüklemeden
(streaming) sayfa sayfa gezmeyi ve içinde arama yapmayı sağlayan ayrı bir pencere.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from core.wordlist_manager import wordlist_manager
from gui import theme
from gui.widgets import BackgroundTask, LabeledEntry, LogConsole, PrimaryButton, SecondaryButton

PAGE_SIZE = 500
# Bu satır sayısının üzerinde "Tümünü Göster" öncesi kullanıcıya onay sorulur —
# Tkinter metin kutusuna onlarca bin satırı tek seferde basmak arayüzü kısa süreliğine kilitleyebilir.
LARGE_FILE_WARNING_THRESHOLD = 20_000


class WordlistViewerWindow(ctk.CTkToplevel):
    """Tek bir wordlist dosyasını gezmek için açılan bağımsız pencere."""

    def __init__(self, master, path: Path) -> None:
        super().__init__(master)
        self.path = path
        self._task = BackgroundTask(self)
        self._page_start = 1  # 1-indexed, o an ekranda gösterilen aralığın başlangıcı

        self.title(f"Wordlist Görüntüleyici — {path.name}")
        self.geometry("760x680")
        self.minsize(560, 420)
        self.configure(fg_color=theme.BG_PRIMARY)
        self.transient(master)

        self._build_ui()
        self.after(50, self._load_stats_and_head)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        ctk.CTkLabel(header, text=self.path.name, font=theme.font(17, "bold"), text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        self.stats_label = ctk.CTkLabel(header, text="Yükleniyor...", font=theme.font(11), text_color=theme.TEXT_MUTED)
        self.stats_label.pack(anchor="w", pady=(2, 0))

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 6))
        search_row.grid_columnconfigure(0, weight=1)
        self.search_entry = LabeledEntry(search_row, "İçinde Ara", "Örn: Pamuk")
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search_entry.entry.bind("<Return>", lambda _e: self._on_search())
        btn_wrap = ctk.CTkFrame(search_row, fg_color="transparent")
        btn_wrap.grid(row=0, column=1, sticky="s", pady=(0, 0))
        PrimaryButton(btn_wrap, text="🔍 Ara", width=90, command=self._on_search).pack(side="left")
        SecondaryButton(btn_wrap, text="✕ Aramayı Temizle", width=140, command=self._load_head).pack(side="left", padx=(8, 0))

        nav_row = ctk.CTkFrame(self, fg_color="transparent")
        nav_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        SecondaryButton(nav_row, text="⏮ Başa Dön", width=110, command=self._load_head).pack(side="left")
        SecondaryButton(nav_row, text="◀ Önceki 500", width=120, command=self._load_prev).pack(side="left", padx=8)
        SecondaryButton(nav_row, text="Sonraki 500 ▶", width=120, command=self._load_next).pack(side="left")
        SecondaryButton(nav_row, text="Sona Git ⏭", width=110, command=self._load_tail).pack(side="left", padx=8)
        PrimaryButton(nav_row, text="📜 Tümünü Göster", width=150, command=self._on_show_all).pack(side="left")

        range_row = ctk.CTkFrame(self, fg_color="transparent")
        range_row.grid(row=3, column=0, sticky="ew", padx=20)
        self.range_label = ctk.CTkLabel(range_row, text="", font=theme.font(11), text_color=theme.TEXT_MUTED, anchor="w")
        self.range_label.pack(anchor="w")

        self.viewer = LogConsole(self, font=theme.font_mono(12))
        self.viewer.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 18))

    # ------------------------------------------------------------------ Veri yükleme
    def _load_stats_and_head(self) -> None:
        def work():
            stats = wordlist_manager.get_wordlist_stats(self.path)
            head = wordlist_manager.get_head(self.path, PAGE_SIZE)
            return stats, head

        def on_done(result):
            stats, head = result
            size_kb = round(stats["file_size_bytes"] / 1024, 1)
            self.stats_label.configure(
                text=f"{stats['total_lines']:,} satır  ·  {size_kb:,} KB  ·  uzunluk {stats['min_length']}-{stats['max_length']} karakter"
            )
            self._total_lines = stats["total_lines"]
            self._render(head, "İlk 500 satır gösteriliyor.")

        def on_error(err):
            self.stats_label.configure(text=f"✖ Dosya okunamadı: {err}")

        self._task.run(work, on_done, on_error)

    def _render(self, lines: list[tuple[int, str]], range_text: str) -> None:
        self.viewer.clear()
        if not lines:
            self.viewer.log("(Bu aralıkta satır yok)", "warning")
            return
        # Binlerce satırda (özellikle 'Tümünü Göster') tek tek log() çağırmak yerine
        # tüm metni tek seferde basmak arayüzün donmasını (satır başına state normal/disabled
        # geçişi) önler.
        text = "\n".join(f"{idx:>7}  {line}" for idx, line in lines) + "\n"
        self.viewer.configure(state="normal")
        self.viewer.insert("end", text)
        self.viewer.configure(state="disabled")
        self._page_start = lines[0][0]
        total = getattr(self, "_total_lines", None)
        total_str = f" / {total:,}" if isinstance(total, int) else ""
        self.range_label.configure(text=f"{range_text}  ({lines[0][0]:,}–{lines[-1][0]:,}{total_str})")

    def _load_head(self) -> None:
        def work():
            return wordlist_manager.get_head(self.path, PAGE_SIZE)
        self._task.run(work, lambda lines: self._render(lines, "İlk 500 satır"))

    def _load_tail(self) -> None:
        def work():
            return wordlist_manager.get_tail(self.path, PAGE_SIZE)
        self._task.run(work, lambda lines: self._render(lines, "Son 500 satır"))

    def _load_next(self) -> None:
        start = self._page_start + PAGE_SIZE

        def work():
            return wordlist_manager.get_range(self.path, start=start, end=start + PAGE_SIZE - 1)

        def on_done(lines):
            if not lines:
                self.range_label.configure(text="Dosyanın sonuna ulaşıldı.")
                return
            self._render(lines, "Sonraki 500 satır")

        self._task.run(work, on_done)

    def _load_prev(self) -> None:
        start = max(1, self._page_start - PAGE_SIZE)
        end = start + PAGE_SIZE - 1

        def work():
            return wordlist_manager.get_range(self.path, start=start, end=end)

        self._task.run(work, lambda lines: self._render(lines, "Önceki 500 satır"))

    def _on_show_all(self) -> None:
        total = getattr(self, "_total_lines", 0)
        if total > LARGE_FILE_WARNING_THRESHOLD:
            proceed = messagebox.askyesno(
                "Büyük Dosya",
                f"Bu liste {total:,} satır içeriyor. Tamamını göstermek biraz sürebilir ve "
                f"arayüzü kısa süreliğine yavaşlatabilir. Devam edilsin mi?",
            )
            if not proceed:
                return

        def work():
            return wordlist_manager.get_range(self.path, start=1, end=None)

        self._task.run(work, lambda lines: self._render(lines, "Tüm liste gösteriliyor"))

    def _on_search(self) -> None:
        query = self.search_entry.get()
        if not query:
            self._load_head()
            return

        def work():
            return wordlist_manager.search_lines(self.path, query, max_results=PAGE_SIZE)

        def on_done(lines):
            self._render(lines, f"'{query}' için arama sonuçları")

        self._task.run(work, on_done)


def open_wordlist_viewer(master, path: Path) -> WordlistViewerWindow:
    """Verilen wordlist dosyası için görüntüleyici pencereyi açar (yoksa oluşturur)."""
    return WordlistViewerWindow(master, path)
