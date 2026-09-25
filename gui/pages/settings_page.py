"""Cybzenor GUI - Ayarlar sayfası: AI motoru kurulumu, wordlist limitleri, depolama konumları."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from config.settings import BASE_DIR, CONFIG_FILE_PATH, settings
from gui import backend, theme
from gui.pages.base import BasePage
from gui.widgets import Card, LabeledEntry, LogConsole, Pill, PrimaryButton, SecondaryButton


def _open_in_file_explorer(path: Path) -> None:
    """Verilen klasörü işletim sisteminin dosya gezgininde açar (yoksa önce oluşturur)."""
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class SettingsPage(BasePage):
    TITLE = "Ayarlar"
    SUBTITLE = "Yapay zeka motoru, üretim limitleri ve depolama konumları."

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._install_running = False
        self._build_ai_card()
        self._build_limits_card()
        self._build_storage_card()

    # ------------------------------------------------------------------ AI Motoru
    def _build_ai_card(self) -> None:
        card = Card(self.scroll, title="Yapay Zeka Motoru",
                    subtitle="Cybzenor herhangi bir bulut API anahtarı kullanmaz. Kendi yerel dil modelinizi "
                             "kurarak (~1GB, tek seferlik) daha isabetli sonuçlar alabilirsiniz.")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        status_row = ctk.CTkFrame(body, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="ew")
        self.ai_pill = Pill(status_row, "Kontrol ediliyor...", kind="muted")
        self.ai_pill.pack(side="left")
        self.install_btn = PrimaryButton(status_row, text="⬇ Yerel AI Modelini Kur", width=220, command=self._on_install)
        self.install_btn.pack(side="left", padx=12)

        self.ai_log = LogConsole(body, height=160)
        self.ai_log.grid(row=1, column=0, sticky="ew", pady=(12, 0))

    def on_show(self) -> None:
        status = backend.ai_engine_status()
        if status["available"]:
            self.ai_pill.configure(text="🧠 Yerel AI Modeli Aktif ve Yüklü", fg_color=theme.ACCENT_SOFT, text_color=theme.ACCENT)
            self.install_btn.configure(text="✔ Zaten Kurulu", state="disabled")
        else:
            self.ai_pill.configure(text="⚠ Yerel AI Modeli Kurulu Değil (kural motoru kullanılıyor)", fg_color="#3a2c0f", text_color=theme.WARNING)
            if not self._install_running:
                self.install_btn.configure(text="⬇ Yerel AI Modelini Kur", state="normal")
        self._render_limits_from_settings()
        self._render_storage_rows()

    def _on_install(self) -> None:
        if self._install_running:
            return
        self._install_running = True
        self.install_btn.configure(state="disabled", text="⏳ Kuruluyor...")
        self.ai_log.clear()
        self.ai_log.log("Model indiriliyor (~1GB, birkaç dakika sürebilir)...", "info")

        # Donmuş bir .exe olarak çalışırken ayrı bir 'python setup_local_ai.py' süreci
        # başlatılamaz (kullanıcının Python'u bile kurulu olmayabilir) — bu durumda
        # model indirme fonksiyonu doğrudan (aynı süreç içinde) çağrılır; llama-cpp-python
        # zaten .exe içine gömülüdür (bkz. build_exe.py), ayrıca pip kurulumu gerekmez.
        is_frozen = getattr(sys, "frozen", False)

        def stream():
            if is_frozen:
                self._install_in_process()
                return
            script = BASE_DIR / "setup_local_ai.py"
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(script)], cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                )
                for line in proc.stdout:  # type: ignore[union-attr]
                    line = line.rstrip("\n")
                    if line:
                        self.after(0, lambda l=line: self.ai_log.log(l))
                proc.wait()
                ok = proc.returncode == 0
            except Exception as e:
                ok = False
                self.after(0, lambda: self.ai_log.log(f"✖ Kurulum başlatılamadı: {e}", "error"))

            self.after(0, lambda: self._finish_install(ok))

        threading.Thread(target=stream, daemon=True).start()

    def _install_in_process(self) -> None:
        """.exe modunda (ayrı python süreci olmadan) modeli doğrudan aynı süreçte indirir."""
        try:
            from ai.local_llm_engine import download_model
            download_model()
            ok = True
        except Exception as e:
            ok = False
            self.after(0, lambda: self.ai_log.log(f"✖ İndirme başarısız: {e}", "error"))
        self.after(0, lambda: self._finish_install(ok))

    def _finish_install(self, ok: bool) -> None:
        self._install_running = False
        if ok:
            self.ai_log.log("✔ Kurulum tamamlandı!", "success")
        else:
            self.ai_log.log("✖ Kurulum başarısız oldu. Yukarıdaki günlüğü inceleyin.", "error")
        self.on_show()

    # ------------------------------------------------------------------ Üretim Limitleri
    def _build_limits_card(self) -> None:
        card = Card(self.scroll, title="Wordlist Üretim Limitleri",
                    subtitle="config/config.json dosyasına kaydedilir; tüm sayfalardaki üretimleri etkiler.")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure((0, 1), weight=1)

        self.e_min_len = LabeledEntry(body, "Varsayılan Min. Uzunluk", "")
        self.e_min_len.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.e_max_len = LabeledEntry(body, "Varsayılan Maks. Uzunluk", "")
        self.e_max_len.grid(row=0, column=1, sticky="ew", pady=6)

        self.e_max_candidates = LabeledEntry(body, "Maksimum Aday Limiti (üretimde kesilir)", "")
        self.e_max_candidates.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.e_max_failures = LabeledEntry(body, "Güvenlik: Maks. Ardışık Başarısızlık", "")
        self.e_max_failures.grid(row=1, column=1, sticky="ew", pady=6)

        SecondaryButton(body, text="💾 Kaydet", width=140, command=self._on_save_limits).grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _render_limits_from_settings(self) -> None:
        self.e_min_len.set(str(settings.wordlist.min_length))
        self.e_max_len.set(str(settings.wordlist.max_length))
        self.e_max_candidates.set(str(settings.wordlist.max_candidates))
        self.e_max_failures.set(str(settings.safety.max_consecutive_failures))

    def _on_save_limits(self) -> None:
        try:
            min_len = int(self.e_min_len.get())
            max_len = int(self.e_max_len.get())
            max_candidates = int(self.e_max_candidates.get())
            max_failures = int(self.e_max_failures.get())
        except ValueError:
            messagebox.showerror("Geçersiz Değer", "Tüm alanlar sayısal olmalıdır.")
            return
        if max_len < min_len:
            messagebox.showerror("Geçersiz Değer", "Maks. uzunluk, min. uzunluktan küçük olamaz.")
            return

        data = {}
        if CONFIG_FILE_PATH.is_file():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data.setdefault("wordlist", {})
        data["wordlist"]["min_length"] = min_len
        data["wordlist"]["max_length"] = max_len
        data["wordlist"]["max_candidates"] = max_candidates
        data.setdefault("safety", {})
        data["safety"]["max_consecutive_failures"] = max_failures

        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        settings.wordlist.min_length = min_len
        settings.wordlist.max_length = max_len
        settings.wordlist.max_candidates = max_candidates
        settings.safety.max_consecutive_failures = max_failures

        messagebox.showinfo("Kaydedildi", "Ayarlar başarıyla kaydedildi.")

    # ------------------------------------------------------------------ Depolama
    def _build_storage_card(self) -> None:
        card = Card(
            self.scroll, title="Verileriniz ve Depolama",
            subtitle="🔒 Tüm veriler yalnızca bu bilgisayarda, proje klasörü içinde saklanır. Hiçbir veri "
                     "internete/bir sunucuya gönderilmez ve başka kullanıcılarla paylaşılmaz."
        )
        card.grid(row=2, column=0, sticky="ew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.storage_rows = ctk.CTkFrame(body, fg_color="transparent")
        self.storage_rows.grid(row=0, column=0, sticky="ew")
        self.storage_rows.grid_columnconfigure(1, weight=1)

    _STORAGE_ITEMS = [
        ("📄", "Üretilen Wordlist'ler", "wordlists/generated", "*.txt", "liste"),
        ("🎯", "Hedef Profilleriniz", "data/synthetic_profiles", "*.json", "hedef"),
        ("🧠", "Yerel AI Modeli", "models", "*.gguf", "model dosyası"),
        ("🗒️", "Loglar", "logs", "*", "dosya"),
    ]

    def _render_storage_rows(self) -> None:
        for w in self.storage_rows.winfo_children():
            w.destroy()

        for i, (icon, label, rel_path, glob_pattern, unit) in enumerate(self._STORAGE_ITEMS):
            full_path = BASE_DIR / rel_path
            count = len(list(full_path.glob(glob_pattern))) if full_path.is_dir() else 0

            row = ctk.CTkFrame(self.storage_rows, fg_color=theme.BG_SECONDARY, corner_radius=10)
            row.grid(row=i, column=0, sticky="ew", pady=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text=icon, font=theme.font(16)).grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=10)

            ctk.CTkLabel(row, text=label, font=theme.font(13, "bold"), text_color=theme.TEXT_PRIMARY, anchor="w") \
                .grid(row=0, column=1, sticky="w", pady=(10, 0))
            count_text = f"{count:,} {unit}" if count else "boş"
            ctk.CTkLabel(row, text=f"{count_text}  ·  ./{rel_path}", font=theme.font(11), text_color=theme.TEXT_SECONDARY, anchor="w") \
                .grid(row=1, column=1, sticky="w", pady=(0, 10))

            SecondaryButton(
                row, text="📂 Klasörü Aç", width=130, height=28, font=theme.font(11), corner_radius=6,
                command=lambda p=full_path: _open_in_file_explorer(p),
            ).grid(row=0, column=2, rowspan=2, padx=(0, 14))
