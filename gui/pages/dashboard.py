"""Cybzenor GUI - Dashboard: hedef profilleri ve üretilmiş wordlist'lerin genel görünümü."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from gui import backend, theme
from gui.pages.base import BasePage
from gui.pages.wordlist_viewer import open_wordlist_viewer
from gui.widgets import Card, Pill, DangerButton, SecondaryButton


class DashboardPage(BasePage):
    TITLE = "Hedefler & Genel Bakış"
    SUBTITLE = "Kayıtlı hedef profilleri ve üretilmiş wordlist'lerinizi buradan yönetin."

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._build_stats_row()
        self._build_targets_card()
        self._build_wordlists_card()

    # ------------------------------------------------------------------ Üst istatistik şeridi
    def _build_stats_row(self) -> None:
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        row.grid_columnconfigure((0, 1, 2), weight=1)

        self._stat_targets = self._stat_card(row, "🎯", "Kayıtlı Hedef", "0", 0)
        self._stat_wordlists = self._stat_card(row, "📄", "Üretilmiş Liste", "0", 1)
        self._stat_ai = self._stat_card(row, "🧠", "AI Motoru", "—", 2)

    def _stat_card(self, parent, icon: str, label: str, value: str, col: int) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=14, border_width=1, border_color=theme.BORDER)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
        ctk.CTkLabel(card, text=icon, font=theme.font(22)).pack(anchor="w", padx=16, pady=(14, 0))
        value_lbl = ctk.CTkLabel(card, text=value, font=theme.font(22, "bold"), text_color=theme.TEXT_PRIMARY)
        value_lbl.pack(anchor="w", padx=16)
        ctk.CTkLabel(card, text=label, font=theme.font(11), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 14))
        return value_lbl

    # ------------------------------------------------------------------ Hedefler kartı
    def _build_targets_card(self) -> None:
        self.targets_card = Card(self.scroll, title="Kayıtlı Hedef Profilleri",
                                  subtitle="AI Hedefli Liste Üretimi sayfasında oluşturduğunuz hedefler burada listelenir.")
        self.targets_card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.targets_list = ctk.CTkFrame(self.targets_card.body, fg_color="transparent")
        self.targets_list.grid(row=0, column=0, sticky="ew")
        self.targets_list.grid_columnconfigure(0, weight=1)

    def _render_targets(self) -> None:
        for w in self.targets_list.winfo_children():
            w.destroy()

        records = backend.list_target_records()
        self._stat_targets.configure(text=str(len(records)))

        if not records:
            ctk.CTkLabel(
                self.targets_list, text="Henüz kayıtlı hedef yok. 'AI Hedefli Liste Üretimi' sayfasından bir tane oluşturun.",
                font=theme.font(12), text_color=theme.TEXT_MUTED
            ).grid(row=0, column=0, sticky="w", pady=8)
            return

        for i, rec in enumerate(records):
            row = ctk.CTkFrame(self.targets_list, fg_color=theme.BG_SECONDARY, corner_radius=10)
            row.grid(row=i, column=0, sticky="ew", pady=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text="🎯", font=theme.font(16)).grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=10)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=1, sticky="w", pady=(10, 0))
            ctk.CTkLabel(info, text=rec.target_name, font=theme.font(14, "bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

            summary = rec.profile.to_summary_dict()
            detail_text = " · ".join(f"{k}: {v}" for k, v in summary.items() if v)
            ctk.CTkLabel(row, text=detail_text or "Profil boş", font=theme.font(11), text_color=theme.TEXT_SECONDARY) \
                .grid(row=1, column=1, sticky="w", pady=(0, 10))

            pill_kind = "success" if rec.has_hash else "muted"
            pill_text = "Test parolası kayıtlı" if rec.has_hash else "Test parolası yok"
            Pill(row, pill_text, kind=pill_kind).grid(row=0, column=2, rowspan=2, padx=10)

            del_btn = ctk.CTkButton(
                row, text="Sil", width=56, height=28, fg_color="transparent",
                hover_color=theme.DANGER, text_color=theme.DANGER, border_width=1, border_color=theme.DANGER,
                font=theme.font(11), corner_radius=6,
                command=lambda r=rec: self._delete_target(r),
            )
            del_btn.grid(row=0, column=3, rowspan=2, padx=(0, 14))

    def _delete_target(self, record: backend.TargetRecord) -> None:
        if messagebox.askyesno("Hedefi Sil", f"'{record.target_name}' hedefi kalıcı olarak silinsin mi?"):
            backend.delete_target_record(record.path)
            self._render_targets()

    # ------------------------------------------------------------------ Wordlist'ler kartı
    def _build_wordlists_card(self) -> None:
        self.wordlists_card = Card(self.scroll, title="Wordlist'leriniz",
                                    subtitle="Varsayılan liste her zaman en üstte sabittir; üretilen listeler en yeniden en eskiye sıralanır.")
        self.wordlists_card.grid(row=2, column=0, sticky="ew")
        self.wordlists_list = ctk.CTkFrame(self.wordlists_card.body, fg_color="transparent")
        self.wordlists_list.grid(row=0, column=0, sticky="ew")
        self.wordlists_list.grid_columnconfigure(0, weight=1)

    _TYPE_ICONS = {"AI_TARGETED": "🧠", "HYBRID": "🧬", "MERGED": "🧬", "DEFAULT": "🗂️"}

    def _render_wordlists(self) -> None:
        for w in self.wordlists_list.winfo_children():
            w.destroy()

        generated = backend.wordlist_manager.list_generated_wordlists()
        self._stat_wordlists.configure(text=str(len(generated)))

        default_path = backend.DEFAULT_WORDLIST
        row_i = 0
        if default_path.is_file():
            self._render_wordlist_row(row_i, {
                "name": default_path.name,
                "path": default_path,
                "size_bytes": default_path.stat().st_size,
                "mtime_str": "Varsayılan Liste",
                "total_candidates": backend.wordlist_line_count(default_path),
                "type": "DEFAULT",
            }, deletable=False)
            row_i += 1

        if not generated and not default_path.is_file():
            ctk.CTkLabel(
                self.wordlists_list, text="Henüz üretilmiş bir liste yok.",
                font=theme.font(12), text_color=theme.TEXT_MUTED
            ).grid(row=0, column=0, sticky="w", pady=8)
            return

        for item in generated[:12]:
            self._render_wordlist_row(row_i, item, deletable=True)
            row_i += 1

    def _render_wordlist_row(self, row_i: int, item: dict, deletable: bool) -> None:
        row = ctk.CTkFrame(self.wordlists_list, fg_color=theme.BG_SECONDARY, corner_radius=10)
        row.grid(row=row_i, column=0, sticky="ew", pady=4)
        row.grid_columnconfigure(1, weight=1)

        type_icon = self._TYPE_ICONS.get(item["type"], "📄")
        ctk.CTkLabel(row, text=type_icon, font=theme.font(16)).grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=10)

        name_lbl = ctk.CTkLabel(row, text=item["name"], font=theme.font(13, "bold"), text_color=theme.TEXT_PRIMARY, cursor="hand2")
        name_lbl.grid(row=0, column=1, sticky="w", pady=(10, 0))
        size_kb = round(item["size_bytes"] / 1024, 1)
        count = item["total_candidates"]
        count_txt = f"{count:,} aday · " if count else ""
        detail_lbl = ctk.CTkLabel(
            row, text=f"{count_txt}{size_kb} KB · {item['mtime_str']}  ·  görüntülemek için tıklayın",
            font=theme.font(11), text_color=theme.TEXT_SECONDARY, cursor="hand2"
        )
        detail_lbl.grid(row=1, column=1, sticky="w", pady=(0, 10))
        for widget in (name_lbl, detail_lbl):
            widget.bind("<Button-1>", lambda _e, p=item["path"]: self._open_viewer(p))

        SecondaryButton(
            row, text="👁 Görüntüle", width=100, height=28, font=theme.font(11), corner_radius=6,
            command=lambda p=item["path"]: self._open_viewer(p),
        ).grid(row=0, column=2, rowspan=2, padx=(0, 8))

        if deletable:
            DangerButton(
                row, text="Sil", width=56, height=28, font=theme.font(11), corner_radius=6,
                command=lambda p=item["path"]: self._delete_wordlist(p),
            ).grid(row=0, column=3, rowspan=2, padx=(0, 14))
        else:
            Pill(row, "Sabit", kind="muted").grid(row=0, column=3, rowspan=2, padx=(0, 14))

    def _open_viewer(self, path) -> None:
        open_wordlist_viewer(self.app, path)

    def _delete_wordlist(self, path) -> None:
        if messagebox.askyesno("Listeyi Sil", f"'{path.name}' kalıcı olarak silinsin mi?"):
            try:
                path.unlink(missing_ok=True)
                meta = path.with_suffix(path.suffix + ".metadata.json")
                meta.unlink(missing_ok=True)
            except Exception as e:
                messagebox.showerror("Hata", str(e))
            self._render_wordlists()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._render_targets()
        self._render_wordlists()
        status = backend.ai_engine_status()
        self._stat_ai.configure(text="Aktif" if status["available"] else "Offline")
