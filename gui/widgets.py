"""
Cybzenor GUI - Ortak Bileşenler
Sayfalar arasında tekrar kullanılan kart, log konsolu, thread yardımcıları ve
istatistik rozeti gibi küçük yapı taşları.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Optional

import customtkinter as ctk

from gui import theme


class Card(ctk.CTkFrame):
    """Köşeleri yuvarlatılmış, başlıklı bölüm kartı. İçerik `self.body`'ye eklenir."""

    def __init__(self, master, title: str = "", subtitle: str = "", **kwargs):
        kwargs.setdefault("fg_color", theme.BG_CARD)
        kwargs.setdefault("corner_radius", 14)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.BORDER)
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        row = 0
        if title:
            ctk.CTkLabel(
                self, text=title, font=theme.font(16, "bold"), text_color=theme.TEXT_PRIMARY, anchor="w"
            ).grid(row=row, column=0, sticky="ew", padx=18, pady=(16, 0))
            row += 1
        if subtitle:
            ctk.CTkLabel(
                self, text=subtitle, font=theme.font(12), text_color=theme.TEXT_SECONDARY,
                anchor="w", justify="left", wraplength=520
            ).grid(row=row, column=0, sticky="ew", padx=18, pady=(2, 0))
            row += 1

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=row, column=0, sticky="nsew", padx=18, pady=16)
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(row, weight=1)


class Pill(ctk.CTkLabel):
    """Küçük durum rozeti (örn: 'AI Aktif', 'Offline')."""

    def __init__(self, master, text: str, kind: str = "info", **kwargs):
        colors = {
            "success": (theme.ACCENT_SOFT, theme.ACCENT),
            "warning": ("#3a2c0f", theme.WARNING),
            "danger": ("#3a1418", theme.DANGER),
            "info": ("#12283f", theme.INFO),
            "muted": (theme.BG_SECONDARY, theme.TEXT_SECONDARY),
        }
        bg, fg = colors.get(kind, colors["info"])
        super().__init__(
            master, text=f"  {text}  ", fg_color=bg, text_color=fg,
            font=theme.font(11, "bold"), corner_radius=8, **kwargs
        )


class LogConsole(ctk.CTkTextbox):
    """Salt-okunur, renkli işlem günlüğü konsolu. Thread'lerden `log()` ile güvenle beslenir."""

    TAG_COLORS = {
        "info": theme.TEXT_SECONDARY,
        "success": theme.ACCENT,
        "warning": theme.WARNING,
        "error": theme.DANGER,
        "default": theme.TEXT_PRIMARY,
    }

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_PRIMARY)
        kwargs.setdefault("text_color", theme.TEXT_PRIMARY)
        kwargs.setdefault("font", theme.font_mono(12))
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("wrap", "word")
        super().__init__(master, **kwargs)
        self.configure(state="disabled")
        for tag, color in self.TAG_COLORS.items():
            self.tag_config(tag, foreground=color)

    def log(self, message: str, level: str = "default") -> None:
        self.configure(state="normal")
        self.insert("end", message + "\n", level)
        self.configure(state="disabled")
        self.see("end")

    def clear(self) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")


class BackgroundTask:
    """
    Uzun süren core işlemlerini (wordlist üretimi, hash denetimi, canlı login vb.)
    ayrı bir thread'de koşturup sonucu/hataları ana (UI) thread'ine güvenle taşıyan
    minimal yardımcı. Tkinter widget'ları SADECE ana thread'den güncellenebildiği
    için `queue` + `after()` polling deseni kullanılır.
    """

    def __init__(self, widget: ctk.CTkBaseClass):
        self._widget = widget
        self._queue: "queue.Queue[Any]" = queue.Queue()
        self._poll_ms = 80

    def run(
        self,
        work_fn: Callable[[], Any],
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        def _worker():
            try:
                result = work_fn()
                self._queue.put(("done", result))
            except Exception as e:  # noqa: BLE001 - hatayı UI'ya taşımak için kasıtlı geniş yakalama
                self._queue.put(("error", e))

        threading.Thread(target=_worker, daemon=True).start()
        self._poll(on_done, on_error)

    def _poll(self, on_done, on_error) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self._widget.after(self._poll_ms, lambda: self._poll(on_done, on_error))
            return

        if kind == "done" and on_done:
            on_done(payload)
        elif kind == "error" and on_error:
            on_error(payload)


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.ACCENT)
        kwargs.setdefault("hover_color", theme.ACCENT_HOVER)
        kwargs.setdefault("text_color", "#04140d")
        kwargs.setdefault("font", theme.font(13, "bold"))
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("height", 38)
        super().__init__(master, **kwargs)


class SecondaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_SECONDARY)
        kwargs.setdefault("hover_color", theme.BG_CARD_HOVER)
        kwargs.setdefault("text_color", theme.TEXT_PRIMARY)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.BORDER)
        kwargs.setdefault("font", theme.font(13))
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("height", 38)
        super().__init__(master, **kwargs)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.DANGER)
        kwargs.setdefault("hover_color", theme.DANGER_HOVER)
        kwargs.setdefault("text_color", "#210306")
        kwargs.setdefault("font", theme.font(13, "bold"))
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("height", 38)
        super().__init__(master, **kwargs)


class LabeledEntry(ctk.CTkFrame):
    """Etiket + tek satır giriş kutusu + (isteğe bağlı) açıklayıcı yardım metni birleşimi."""

    def __init__(
        self, master, label: str, placeholder: str = "", show: Optional[str] = None,
        help_text: str = "", **kwargs
    ):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=theme.font(12, "bold"), text_color=theme.TEXT_SECONDARY, anchor="w") \
            .grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.entry = ctk.CTkEntry(
            self, placeholder_text=placeholder, show=show, font=theme.font(13),
            fg_color=theme.BG_SECONDARY, border_color=theme.BORDER, height=36, **kwargs
        )
        self.entry.grid(row=1, column=0, sticky="ew")
        if help_text:
            ctk.CTkLabel(
                self, text=help_text, font=theme.font(10), text_color=theme.TEXT_MUTED,
                anchor="w", justify="left", wraplength=400
            ).grid(row=2, column=0, sticky="ew", pady=(3, 0))

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class CollapsibleSection(ctk.CTkFrame):
    """
    Başlığa tıklanınca açılıp kapanan bölüm. Az kullanılan/ileri seviye ayarları
    (örn. CSRF, gecikme) varsayılan olarak gizleyip formu sadeleştirmek için kullanılır.
    İçerik `self.body`'ye eklenir.
    """

    def __init__(self, master, title: str, expanded: bool = False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._title = title
        self._expanded = expanded

        self.toggle_btn = ctk.CTkButton(
            self, text=self._arrow_text(), anchor="w", fg_color=theme.BG_SECONDARY,
            hover_color=theme.BG_CARD_HOVER, text_color=theme.TEXT_SECONDARY,
            font=theme.font(12, "bold"), corner_radius=8, height=32, command=self.toggle,
        )
        self.toggle_btn.grid(row=0, column=0, sticky="ew")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid_columnconfigure((0, 1), weight=1)
        if self._expanded:
            self.body.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    def _arrow_text(self) -> str:
        return f"{'▾' if self._expanded else '▸'}  {self._title}"

    def toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self.body.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        else:
            self.body.grid_remove()
        self.toggle_btn.configure(text=self._arrow_text())


def split_csv(text: str) -> list[str]:
    """'Ahmet, Ayşe Pamuk' gibi virgül/boşluk ayraçlı girdiyi temiz bir listeye çevirir
    (main.py'deki CLI giriş ayrıştırmasıyla aynı kural: [,/&+\\s]+)."""
    import re
    return [p.strip() for p in re.split(r"[,/&+\s]+", text) if len(p.strip()) >= 2]
