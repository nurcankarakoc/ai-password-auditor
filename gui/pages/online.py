"""Cybzenor GUI - Canlı Login Ekranı Denetimi sayfası.

Gerçek bir HTTP login formuna karşı, SafetyController gözetiminde parola denemesi yapar.
Yalnızca kendi sisteminizde veya yazılı izinle yetkilendirildiğiniz hedeflerde kullanın.
"""

from __future__ import annotations

import re
from tkinter import messagebox

import customtkinter as ctk

from config.settings import settings
from core.online_login_auditor import HttpLoginAuditService
from gui import backend, theme
from gui.pages.base import BasePage
from gui.widgets import BackgroundTask, Card, CollapsibleSection, DangerButton, LabeledEntry, LogConsole, Pill, SecondaryButton


class OnlinePage(BasePage):
    TITLE = "Canlı Login Ekranı Denetimi"
    SUBTITLE = "Gerçek bir HTTP login formuna karşı, güvenlik denetleyicisi (SafetyController) gözetiminde parola dener."

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._task = BackgroundTask(self)
        self._probe_status: int | None = None
        self._probe_text: str = ""
        self._service: HttpLoginAuditService | None = None
        self._next_start_index = 0
        self._build_legal_card()
        self._build_form_card()
        self._build_detection_card()
        self._build_run_card()
        self._sync_enabled_state()

    # ------------------------------------------------------------------ Yasal onay
    def _build_legal_card(self) -> None:
        card = Card(self.scroll, subtitle=None)
        card.configure(border_color=theme.DANGER, fg_color="#1c1418")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        body = card.body

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(row, text="⚠️", font=theme.font(22)).pack(side="left", padx=(0, 12), anchor="n")

        text_wrap = ctk.CTkFrame(row, fg_color="transparent")
        text_wrap.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            text_wrap,
            text="Bu özellik GERÇEK bir sisteme ağ üzerinden istek gönderir. Sadece kendi sisteminizde veya "
                 "yazılı izinle yetkilendirildiğiniz hedeflerde kullanın — yetkisiz kullanım suçtur.",
            font=theme.font(12, "bold"), text_color=theme.DANGER, wraplength=850, justify="left", anchor="w"
        ).pack(anchor="w")

        self.confirm_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            text_wrap, text="Bu hedefte test yapma yetkim olduğunu onaylıyorum.", variable=self.confirm_var,
            font=theme.font(12, "bold"), fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            border_color=theme.BORDER, command=self._sync_enabled_state
        ).pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ Form
    def _build_form_card(self) -> None:
        card = Card(self.scroll, title="1. Hedef Login Formu Yapılandırması",
                    subtitle="Bu bilgileri tarayıcınızda hedef giriş sayfasını açıp geliştirici araçlarının "
                             "(F12) 'Network/Ağ' sekmesinden, giriş denedikten sonra görünen isteğe bakarak bulabilirsiniz.")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure((0, 1), weight=1)

        self.e_url = LabeledEntry(
            body, "Hedef Login URL'si", "http://localhost:8080/login",
            help_text="Formun gönderildiği tam adres (tarayıcıda <form action=\"...\"> veya Network sekmesindeki istek adresi)."
        )
        self.e_url.grid(row=0, column=0, columnspan=2, sticky="ew", pady=6)

        self.method_combo = self._labeled_combo(
            body, "HTTP Metodu", ["POST", "GET"], 1, 0,
            help_text="Neredeyse tüm login formları POST kullanır."
        )
        self.content_type_combo = self._labeled_combo(
            body, "İçerik Tipi", ["form", "json"], 1, 1,
            help_text="Klasik HTML formu ise 'form'; API/tek sayfa uygulaması (SPA) ise genelde 'json'."
        )

        self.e_username_field = LabeledEntry(
            body, "Kullanıcı Adı Alan İsmi", "username",
            help_text="HTML'deki <input name=\"...\"> değeri. Sayfa kaynağında ara: 'username', 'email', 'user_login' gibi olabilir."
        )
        self.e_username_field.set("username")
        self.e_username_field.grid(row=2, column=0, sticky="ew", pady=6)
        self.e_username_value = LabeledEntry(
            body, "Denenecek Kullanıcı Adı", "admin",
            help_text="Parolasını test ettiğiniz, yetkili olduğunuz gerçek hesabın kullanıcı adı/e-postası."
        )
        self.e_username_value.grid(row=2, column=1, sticky="ew", pady=6)

        self.e_password_field = LabeledEntry(
            body, "Parola Alan İsmi", "password",
            help_text="HTML'deki parola <input> alanının name değeri (genelde 'password' veya 'pass')."
        )
        self.e_password_field.set("password")
        self.e_password_field.grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)

        advanced = CollapsibleSection(body, "Gelişmiş Ayarlar (CSRF Token, İstek Gecikmesi)")
        advanced.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        adv = advanced.body

        self.e_delay = LabeledEntry(
            adv, "İstekler Arası Bekleme (ms)", str(settings.safety.online_request_delay_ms),
            help_text="Her denemeden önce beklenecek süre — hedefi yormamak ve rate-limit'e takılmamak için."
        )
        self.e_delay.grid(row=0, column=0, columnspan=2, sticky="ew", pady=6)

        self.csrf_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            adv, text="Form bir CSRF token gerektiriyor (her istekte formdan yeniden okunur)", variable=self.csrf_var,
            font=theme.font(12), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, border_color=theme.BORDER,
            command=self._sync_enabled_state
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 6))

        self.e_csrf_field = LabeledEntry(
            adv, "CSRF Alan İsmi", "csrf_token",
            help_text="Formdaki gizli token alanının name değeri."
        )
        self.e_csrf_field.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=6)
        self.e_csrf_regex = LabeledEntry(
            adv, "Token Regex (1 yakalama grubu)", r'name="csrf_token" value="(.*?)"',
            help_text="Sayfa kaynağından token değerini çıkaran regex; parantez () içindeki kısım token'ın kendisi olmalı."
        )
        self.e_csrf_regex.grid(row=2, column=1, sticky="ew", pady=6)

    def _labeled_combo(self, parent, label: str, values: list[str], row: int, col: int, help_text: str = "") -> ctk.CTkComboBox:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0), pady=6)
        ctk.CTkLabel(wrap, text=label, font=theme.font(12, "bold"), text_color=theme.TEXT_SECONDARY, anchor="w").pack(anchor="w", pady=(0, 4))
        combo = ctk.CTkComboBox(
            wrap, values=values, font=theme.font(13), fg_color=theme.BG_SECONDARY,
            border_color=theme.BORDER, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        combo.set(values[0])
        combo.pack(fill="x")
        if help_text:
            ctk.CTkLabel(
                wrap, text=help_text, font=theme.font(10), text_color=theme.TEXT_MUTED,
                anchor="w", justify="left", wraplength=380
            ).pack(anchor="w", pady=(3, 0))
        return combo

    # ------------------------------------------------------------------ Yanıt analizi / tespit
    def _build_detection_card(self) -> None:
        card = Card(self.scroll, title="2. Yanıt Analizi ve Başarı Tespiti",
                    subtitle="Önce bilinçli olarak YANLIŞ bir parolayla tek bir 'sahte deneme' (probe) gönderilir; "
                             "hedefin nasıl cevap verdiğini görmeden başarı tespiti güvenilir olmaz.")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        probe_row = ctk.CTkFrame(body, fg_color="transparent")
        probe_row.grid(row=0, column=0, sticky="ew")
        self.probe_btn = SecondaryButton(probe_row, text="📡 Sahte Deneme Gönder (Probe)", width=220, command=self._on_probe)
        self.probe_btn.pack(side="left")
        self.probe_pill = Pill(probe_row, "Henüz gönderilmedi", kind="muted")
        self.probe_pill.pack(side="left", padx=12)

        self.probe_preview = ctk.CTkLabel(
            body, text="", font=theme.font(11), text_color=theme.TEXT_MUTED, wraplength=900, justify="left", anchor="w"
        )
        self.probe_preview.grid(row=1, column=0, sticky="ew", pady=(8, 12))

        self.detect_mode = ctk.CTkSegmentedButton(
            body, values=["Otomatik (Önerilen)", "Belirteç Ara", "Sadece HTTP Status"],
            font=theme.font(12), fg_color=theme.BG_SECONDARY, selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER, unselected_color=theme.BG_SECONDARY,
            command=lambda _=None: self._sync_enabled_state(),
        )
        self.detect_mode.set("Otomatik (Önerilen)")
        self.detect_mode.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        indicator_row = ctk.CTkFrame(body, fg_color="transparent")
        indicator_row.grid(row=3, column=0, sticky="ew")
        indicator_row.grid_columnconfigure((0, 1), weight=1)
        self.e_indicator = LabeledEntry(indicator_row, "Belirteç Metni (en az 4 karakter)", "örn: 'Hatalı şifre' veya 'Dashboard'")
        self.e_indicator.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.indicator_kind = self._labeled_combo(
            indicator_row, "Bu Metin...", ["Doğru girişte görünür (başarı belirteci)", "Yanlış girişte görünür (hata belirteci)"], 0, 1
        )

    def _on_probe(self) -> None:
        if not self._require_basics():
            return
        self.probe_btn.configure(state="disabled", text="⏳ Gönderiliyor...")
        self.probe_pill.configure(text="Gönderiliyor...")

        def work():
            service = self._build_service(request_delay_ms=0)
            status, text, _ = service.attempt_login("cybzenor_probe_kasitli_yanlis_9231")
            return status, text

        def on_done(result):
            status, text = result
            self._probe_status, self._probe_text = status, text
            self.probe_btn.configure(state="normal", text="📡 Sahte Deneme Gönder (Probe)")
            self.probe_pill.configure(text=f"HTTP {status}")
            snippet = re.sub(r"\s+", " ", text).strip()[:280] or "(boş yanıt)"
            self.probe_preview.configure(text=f"Yanıt önizleme: {snippet}")
            if status in (200, 301, 302, 303):
                self.probe_preview.configure(
                    text=self.probe_preview.cget("text") +
                    "\n⚠ DİKKAT: Yanlış parolada bile başarı kodu döndü — 'Sadece HTTP Status' modu burada YANLIŞ POZİTİF üretir."
                )
            self._sync_enabled_state()

        def on_error(err: Exception):
            self.probe_btn.configure(state="normal", text="📡 Sahte Deneme Gönder (Probe)")
            self.probe_pill.configure(text="Hata")
            self.probe_preview.configure(text=f"✖ Probe başarısız (ağ hatası olabilir): {err}")

        self._task.run(work, on_done, on_error)

    # ------------------------------------------------------------------ Çalıştırma
    def _build_run_card(self) -> None:
        card = Card(self.scroll, title="3. Wordlist ve Güvenlik Eşiği")
        card.grid(row=3, column=0, sticky="ew")
        body = card.body
        body.grid_columnconfigure((0, 1), weight=1)

        self.wordlist_combo = self._labeled_combo(
            body, "Wordlist", ["(Wordlist yok)"], 0, 0,
            help_text="Denenecek parola adayları listesi (Dashboard'da 👁 ile içeriğini önizleyebilirsiniz)."
        )
        self.e_threshold = LabeledEntry(
            body, "Maks. Ardışık Başarısızlık Eşiği", str(settings.safety.max_consecutive_failures),
            help_text="Bu kadar art arda hatalı denemeden sonra denetim otomatik durur (hedefi korumak için)."
        )
        self.e_threshold.set(str(settings.safety.max_consecutive_failures))
        self.e_threshold.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=6)

        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.run_btn = DangerButton(action_row, text="🌐 Denetimi Başlat", width=200, command=self._on_run)
        self.run_btn.pack(side="left")
        self.continue_btn = SecondaryButton(action_row, text="▶ Kaldığı Yerden Devam Et", width=200, command=self._on_continue)
        # Yalnızca MAX_CONSECUTIVE_FAILURES_EXCEEDED ile durduğunda gösterilir (bkz. _render_report).
        self.progress = ctk.CTkProgressBar(action_row, mode="indeterminate", width=200, fg_color=theme.BG_SECONDARY, progress_color=theme.DANGER)
        self.progress.pack(side="left", padx=6)

        self.log = LogConsole(body, height=200)
        self.log.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))

    def on_show(self) -> None:
        self._wordlist_paths = backend.list_all_wordlists()
        names = [p.name for p in self._wordlist_paths] or ["(Wordlist yok)"]
        self.wordlist_combo.configure(values=names)
        self.wordlist_combo.set(names[0])
        self._sync_enabled_state()

    def _require_basics(self) -> bool:
        if not self.confirm_var.get():
            messagebox.showwarning("Yetki Onayı Gerekli", "Devam etmeden önce yetki onay kutusunu işaretlemelisiniz.")
            return False
        if not self.e_url.get():
            messagebox.showwarning("URL Gerekli", "Hedef login URL'sini girin.")
            return False
        if not self.e_username_value.get():
            messagebox.showwarning("Kullanıcı Adı Gerekli", "Denenecek kullanıcı adını girin.")
            return False
        return True

    def _sync_enabled_state(self) -> None:
        enabled = self.confirm_var.get()
        state = "normal" if enabled else "disabled"
        self.probe_btn.configure(state=state)
        self.run_btn.configure(state=state)

        show_csrf = self.csrf_var.get()
        (self.e_csrf_field.grid if show_csrf else self.e_csrf_field.grid_remove)()
        (self.e_csrf_regex.grid if show_csrf else self.e_csrf_regex.grid_remove)()

        show_indicator = self.detect_mode.get() == "Belirteç Ara"
        if hasattr(self, "e_indicator"):
            frame = self.e_indicator.master
            (frame.grid if show_indicator else frame.grid_remove)()

    def _build_service(self, request_delay_ms: int | None = None) -> HttpLoginAuditService:
        delay = request_delay_ms
        if delay is None:
            delay_txt = self.e_delay.get()
            delay = int(delay_txt) if delay_txt.isdigit() else None

        return HttpLoginAuditService(
            target_url=self.e_url.get(),
            username_field=self.e_username_field.get() or "username",
            username_value=self.e_username_value.get(),
            password_field=self.e_password_field.get() or "password",
            method=self.method_combo.get(),
            content_type=self.content_type_combo.get(),
            csrf_field=self.e_csrf_field.get() or None if self.csrf_var.get() else None,
            csrf_regex=self.e_csrf_regex.get() or None if self.csrf_var.get() else None,
            request_delay_ms=delay,
        )

    def _detection_kwargs(self) -> dict:
        mode = self.detect_mode.get()
        if mode == "Belirteç Ara":
            text = self.e_indicator.get()
            if len(text.replace(" ", "")) < 4:
                raise ValueError("Belirteç metni en az 4 karakter olmalı (yanlış pozitif riskini azaltmak için).")
            if self.indicator_kind.get().startswith("Doğru"):
                return {"success_indicator": text}
            return {"failure_indicator": text}
        if mode == "Sadece HTTP Status":
            return {}
        # Otomatik
        if self._probe_status in (None, 0):
            raise ValueError("Otomatik mod için önce başarılı bir 'Sahte Deneme (Probe)' göndermelisiniz.")
        return {
            "auto_baseline_status": self._probe_status,
            "auto_baseline_word_count": len(self._probe_text.split()),
        }

    def _on_run(self) -> None:
        if not self._require_basics():
            return
        if not self._wordlist_paths:
            messagebox.showwarning("Wordlist Yok", "Önce bir wordlist üretin.")
            return
        try:
            detection_kwargs = self._detection_kwargs()
        except ValueError as e:
            messagebox.showerror("Eksik/Geçersiz Ayar", str(e))
            return

        wl_idx = self.wordlist_combo.cget("values").index(self.wordlist_combo.get())
        wordlist_path = self._wordlist_paths[wl_idx]
        try:
            threshold = int(self.e_threshold.get())
        except ValueError:
            threshold = settings.safety.max_consecutive_failures

        self.log.clear()
        self.continue_btn.pack_forget()
        self._next_start_index = 0
        self.log.log("Canlı denetim başlatılıyor (SafetyController gözetiminde)...", "info")
        self._run_round(detection_kwargs, wordlist_path, threshold, start_index=0)

    def _on_continue(self) -> None:
        try:
            detection_kwargs = self._detection_kwargs()
            threshold = int(self.e_threshold.get())
        except ValueError as e:
            messagebox.showerror("Hata", str(e))
            return
        wl_idx = self.wordlist_combo.cget("values").index(self.wordlist_combo.get())
        wordlist_path = self._wordlist_paths[wl_idx]
        self.continue_btn.pack_forget()
        self.log.log(f"Kaldığı yerden ({self._next_start_index}. adaydan itibaren) devam ediliyor...", "info")
        self._run_round(detection_kwargs, wordlist_path, threshold, start_index=self._next_start_index)

    def _run_round(self, detection_kwargs: dict, wordlist_path, threshold: int, start_index: int) -> None:
        self.run_btn.configure(state="disabled", text="⏳ Çalışıyor...")
        self.progress.start()

        def work():
            service = self._build_service()
            for k, v in detection_kwargs.items():
                setattr(service, k, v)
            return backend.run_live_login_audit(service, wordlist_path, threshold, start_index=start_index)

        def on_done(report):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🌐 Denetimi Başlat")
            self._render_report(report)

        def on_error(err: Exception):
            self.progress.stop()
            self.run_btn.configure(state="normal", text="🌐 Denetimi Başlat")
            self.log.log(f"✖ Hata: {err}", "error")
            messagebox.showerror("Denetim Hatası", str(err))

        self._task.run(work, on_done, on_error)

    def _render_report(self, report: dict) -> None:
        status = report["status"]
        if status == "MATCH_FOUND":
            self.log.log("✔ PAROLA BAŞARIYLA TESPİT EDİLDİ!", "success")
            self.log.log(f"  Açık parola   : {report['matched_password']}", "success")
            self.log.log(f"  Deneme sayısı : {report['attempts_made']:,}", "default")
            self.log.log(f"  Geçen süre    : {report['elapsed_seconds']} sn", "default")
        elif status.startswith("SAFETY_HALTED"):
            trip_reason = report["safety_status"].get("trip_reason")
            self.log.log("⚠ TEST GÜVENLİK PROTOKOLÜ GEREĞİ DURDURULDU", "warning")
            self.log.log(f"  Durum         : {status}", "default")
            self.log.log(f"  Açıklama      : {report['error_message']}", "default")
            self.log.log(f"  Yapılan deneme: {report['attempts_made']:,}", "default")
            if trip_reason == "MAX_CONSECUTIVE_FAILURES_EXCEEDED":
                self.log.log("  Bu kendi belirlediğimiz eşik — hedeften gelen gerçek bir engelleme sinyali değil.", "default")
                self._next_start_index = report["next_start_index"]
                self.continue_btn.pack(side="left", padx=10)
            else:
                self.log.log("  Bu, hedeften gelen GERÇEK bir engelleme sinyali — hedefi korumak için devam sunulmuyor.", "warning")
        else:
            self.log.log("✖ Eşleşme bulunamadı.", "error")
            self.log.log(f"  Deneme sayısı : {report['attempts_made']:,}", "default")
            self.log.log(f"  Geçen süre    : {report['elapsed_seconds']} sn", "default")
