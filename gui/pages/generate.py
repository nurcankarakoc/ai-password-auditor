"""Cybzenor GUI - AI Hedefli Liste Üretimi sayfası."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ai.schemas import PasswordPolicy
from gui import backend, theme
from gui.pages.base import BasePage
from gui.pages.wordlist_viewer import open_wordlist_viewer
from gui.widgets import BackgroundTask, Card, LabeledEntry, LogConsole, Pill, PrimaryButton, SecondaryButton, split_csv


class GeneratePage(BasePage):
    TITLE = "Yapay Zeka Hedefli Liste Üretimi"
    SUBTITLE = "Hedef hakkında bildiklerinizi girin; Cybzenor anlamsal olarak tutarlı, önceliklendirilmiş bir parola listesi üretsin."

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._task = BackgroundTask(self)
        self._build_profile_card()
        self._build_notes_card()
        self._build_policy_card()
        self._build_save_card()
        self._build_run_card()

    # ------------------------------------------------------------------ Profil bilgileri
    def _build_profile_card(self) -> None:
        card = Card(self.scroll, title="1. Hedef Profil Bilgileri",
                    subtitle="Birden fazla değeri virgülle ayırarak girin. Hiçbir alan zorunlu değildir.")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure((0, 1), weight=1, uniform="col")

        self.e_names = LabeledEntry(body, "İsimler", "Örn: Ahmet, Ayşe, Pamuk")
        self.e_names.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.e_dates = LabeledEntry(body, "Tarihler (Yıl)", "Örn: 1995, 2021")
        self.e_dates.grid(row=0, column=1, sticky="ew", pady=6)

        self.e_locations = LabeledEntry(body, "Şehir / Plaka", "Örn: İstanbul, 34")
        self.e_locations.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.e_interests = LabeledEntry(body, "İlgi Alanları / Takım", "Örn: Fenerbahçe, gitar, kahve")
        self.e_interests.grid(row=1, column=1, sticky="ew", pady=6)

        self.e_keywords = LabeledEntry(body, "Özel Kelimeler / Renk / Lakap", "Örn: mor, yazılımcı, kartal")
        self.e_keywords.grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)

    # ------------------------------------------------------------------ Serbest metin
    def _build_notes_card(self) -> None:
        card = Card(self.scroll, title="2. Ek Notlar / Serbest Metin (İsteğe Bağlı)",
                    subtitle="Yukarıdaki alanlara sığmayan cümleleri buraya yazın. Yerel AI motoru bu metni okuyup "
                             "yukarıdaki profille otomatik birleştirir.")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        body = card.body

        self.ai_status_pill = Pill(body, "AI durumu kontrol ediliyor...", kind="muted")
        self.ai_status_pill.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.notes_text = ctk.CTkTextbox(
            body, height=90, fg_color=theme.BG_SECONDARY, border_color=theme.BORDER,
            border_width=1, font=theme.font(13), corner_radius=8
        )
        self.notes_text.grid(row=1, column=0, sticky="ew")
        body.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------ Parola politikası
    def _build_policy_card(self) -> None:
        card = Card(self.scroll, title="3. Hedef Sistem Parola Politikası (İsteğe Bağlı)",
                    subtitle="Hedef sistemin kabul etmeyeceği adaylar otomatik elenir.")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.e_min_len = LabeledEntry(body, "Min. Uzunluk", "6")
        self.e_min_len.set("6")
        self.e_min_len.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.e_max_len = LabeledEntry(body, "Maks. Uzunluk", "32")
        self.e_max_len.set("32")
        self.e_max_len.grid(row=0, column=1, sticky="ew", padx=8)

        self.chk_upper = ctk.BooleanVar(value=False)
        self.chk_lower = ctk.BooleanVar(value=False)
        self.chk_digit = ctk.BooleanVar(value=False)
        self.chk_special = ctk.BooleanVar(value=False)

        chk_row = ctk.CTkFrame(body, fg_color="transparent")
        chk_row.grid(row=1, column=0, columnspan=4, sticky="w", pady=(12, 0))
        for text, var in [
            ("Büyük harf zorunlu", self.chk_upper), ("Küçük harf zorunlu", self.chk_lower),
            ("Rakam zorunlu", self.chk_digit), ("Özel karakter zorunlu", self.chk_special),
        ]:
            ctk.CTkCheckBox(
                chk_row, text=text, variable=var, font=theme.font(12),
                fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, border_color=theme.BORDER
            ).pack(side="left", padx=(0, 18))

    # ------------------------------------------------------------------ Kayıt ayarları
    def _build_save_card(self) -> None:
        card = Card(self.scroll, title="4. Kayıt Ayarları",
                    subtitle="Hedef profili tekrar kullanabilmeniz için (Hash Denetim sayfasında) kaydedilir.")
        card.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure((0, 1), weight=1)

        self.e_target_name = LabeledEntry(body, "Hedef Adı / Açıklaması", "Örn: Ahmet - Kurumsal Hesap")
        self.e_target_name.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.e_ground_truth = LabeledEntry(body, "Test Parolası (Ground Truth, isteğe bağlı)", "Sadece test/lab ortamı için", show="•")
        self.e_ground_truth.grid(row=0, column=1, sticky="ew", pady=6)

        self.e_filename = LabeledEntry(body, "Dosya Adı", "otomatik oluşturulur (ör. ai_targeted_ahmet.txt)")
        self.e_filename.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)

    # ------------------------------------------------------------------ Üret butonu + log
    def _build_run_card(self) -> None:
        card = Card(self.scroll, title="5. Üret")
        card.grid(row=4, column=0, sticky="ew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.grid(row=0, column=0, sticky="ew")
        self.run_btn = PrimaryButton(action_row, text="🚀 Wordlist Üret", width=180, command=self._on_generate)
        self.run_btn.pack(side="left")
        self.progress = ctk.CTkProgressBar(action_row, mode="indeterminate", width=220, fg_color=theme.BG_SECONDARY, progress_color=theme.ACCENT)
        self.progress.pack(side="left", padx=16)

        result_row = ctk.CTkFrame(body, fg_color="transparent")
        result_row.grid(row=1, column=0, sticky="ew", pady=(10, 6))
        self.summary_label = ctk.CTkLabel(result_row, text="", font=theme.font(12, "bold"), text_color=theme.ACCENT, anchor="w", justify="left")
        self.summary_label.pack(side="left")
        self.view_btn = SecondaryButton(result_row, text="👁 Listeyi Görüntüle", width=170, command=self._open_last_result)
        self.view_btn.pack(side="left", padx=12)
        self.view_btn.pack_forget()
        self._last_output_path = None

        self.log = LogConsole(body, height=180)
        self.log.grid(row=2, column=0, sticky="ew")

    # ------------------------------------------------------------------ Mantık
    def on_show(self) -> None:
        status = backend.ai_engine_status()
        if status["available"]:
            self.ai_status_pill.configure(text="🧠 Yerel AI Motoru Aktif")
            self._set_pill_kind(self.ai_status_pill, "success")
        else:
            self.ai_status_pill.configure(text=f"⚠ Yerel AI kurulu değil — kural motoru kullanılacak ({backend.ai_setup_hint()})")
            self._set_pill_kind(self.ai_status_pill, "warning")

    @staticmethod
    def _set_pill_kind(pill: Pill, kind: str) -> None:
        colors = {"success": (theme.ACCENT_SOFT, theme.ACCENT), "warning": ("#3a2c0f", theme.WARNING), "muted": (theme.BG_SECONDARY, theme.TEXT_SECONDARY)}
        bg, fg = colors[kind]
        pill.configure(fg_color=bg, text_color=fg)

    def _collect_policy(self) -> PasswordPolicy | None:
        try:
            min_len = int(self.e_min_len.get() or 6)
            max_len = int(self.e_max_len.get() or 32)
        except ValueError:
            messagebox.showerror("Geçersiz Değer", "Min./Maks. uzunluk sayısal olmalıdır.")
            return None
        return PasswordPolicy(
            min_length=min_len, max_length=max_len,
            require_uppercase=self.chk_upper.get(), require_lowercase=self.chk_lower.get(),
            require_digit=self.chk_digit.get(), require_special=self.chk_special.get(),
        )

    def _on_generate(self) -> None:
        names = split_csv(self.e_names.get())
        dates = split_csv(self.e_dates.get())
        locations = split_csv(self.e_locations.get())
        interests = split_csv(self.e_interests.get())
        keywords = split_csv(self.e_keywords.get())
        free_text = self.notes_text.get("1.0", "end").strip()
        target_name = self.e_target_name.get()
        ground_truth = self.e_ground_truth.get()
        filename_hint = self.e_filename.get()

        policy = self._collect_policy()
        if policy is None:
            return
        if not any([names, dates, locations, interests, keywords, free_text]):
            messagebox.showwarning("Boş Profil", "Lütfen en az bir alan doldurun (isim, tarih, ilgi alanı vb.).")
            return

        self.log.clear()
        self.summary_label.configure(text="")
        self.view_btn.pack_forget()
        self.run_btn.configure(state="disabled", text="⏳ Üretiliyor...")
        self.progress.start()
        self.log.log("İşlem başlatıldı...", "info")

        def work():
            profile = backend.build_profile_from_form(names, dates, locations, interests, keywords)
            if free_text:
                profile = backend.enrich_profile_with_free_text(profile, free_text)

            default_slug = profile.names[0].lower() if profile.names else "target"
            filename = backend.safe_wordlist_filename(filename_hint or f"ai_targeted_{default_slug}", "ai_targeted")

            output_path, meta = backend.generate_targeted_wordlist(profile, policy, filename)
            saved_path = backend.save_target_record(target_name, profile, ground_truth)
            return profile, output_path, meta, saved_path

        def on_done(result):
            profile, output_path, meta, saved_path = result
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🚀 Wordlist Üret")

            self.log.log(f"✔ Wordlist üretildi: {output_path.name}", "success")
            self.log.log(f"  Toplam aday       : {meta['total_candidates']:,}", "default")
            pd = meta["priority_distribution"]
            self.log.log(f"  Yüksek öncelik    : {pd['priority_1_high']:,}", "default")
            self.log.log(f"  Orta öncelik      : {pd['priority_2_medium']:,}", "default")
            self.log.log(f"  Düşük/Leet        : {pd['priority_3_low']:,}", "default")
            self.log.log(f"  Süre              : {meta['duration_seconds']} sn", "default")
            self.log.log(f"✔ Hedef profil kaydedildi: {saved_path.name}", "success")
            if meta.get("below_recommended_minimum"):
                self.log.log("⚠ Aday sayısı önerilen minimumun altında — daha fazla bilgi girmeyi deneyin.", "warning")

            self.summary_label.configure(
                text=f"Üretildi: {output_path.name}  •  {meta['total_candidates']:,} aday  •  {meta['duration_seconds']} sn"
            )
            self._last_output_path = output_path
            self.view_btn.pack(side="left", padx=12)

        def on_error(err: Exception):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🚀 Wordlist Üret")
            self.log.log(f"✖ Hata: {err}", "error")
            messagebox.showerror("Üretim Hatası", str(err))

        self._task.run(work, on_done, on_error)

    def _open_last_result(self) -> None:
        if self._last_output_path is not None:
            open_wordlist_viewer(self.app, self._last_output_path)
