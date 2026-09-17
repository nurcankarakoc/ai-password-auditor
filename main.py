"""
Cybzenor - Ana CLI Giriş Noktası
Kullanıcı arayüzü, interaktif menü döngüsü ve operasyonel modül yönlendiricisi.
"""

import sys
import re
import json
import hashlib
from pathlib import Path
from typing import NoReturn, Optional, List, Dict, Any, Tuple
from colorama import Fore, Style

from config.settings import settings, BASE_DIR
from utils.logger import logger
from utils.platform_helper import (
    setup_terminal_encoding,
    clear_screen,
    print_banner,
    print_success,
    print_info,
    print_warning,
    print_error,
    print_header,
    pause_prompt,
)


from core.wordlist_manager import wordlist_manager
from core.cli_commands import execute_fast_command, get_active_target


def display_system_status() -> None:
    """Mevcut sistem ve yapılandırma özetini gösterir."""
    active_target = get_active_target()
    active_str = f"{Fore.GREEN}{Style.BRIGHT}{active_target.upper()}{Style.RESET_ALL}" if active_target else f"{Fore.LIGHTBLACK_EX}Seçilmedi (Tüm hedefler aktif){Style.RESET_ALL}"

    print(f"{Fore.LIGHTBLACK_EX}--- Sistem Yapılandırma Özeti ---")
    print(f" • Aktif Hedef (Workspace): {active_str}")
    print(f" • Parola Uzunluk Sınırı  : {settings.wordlist.min_length} - {settings.wordlist.max_length} karakter")
    print(f" • Maksimum Aday Limiti   : {settings.wordlist.max_candidates:,}")
    print(f" • Log Seviyesi / Maskele : {settings.log_level} / {'Aktif' if settings.mask_sensitive_data else 'Pasif'}")
    print(f" • Güvenlik Hata Eşiği    : {settings.safety.max_consecutive_failures} ardışık deneme")
    print(f"---------------------------------{Style.RESET_ALL}\n")


def display_menu() -> None:
    """Ana menü seçeneklerini yazdırır."""
    print(f"{Fore.YELLOW}{Style.BRIGHT}[ ANA OPERASYON MENÜSÜ ]{Style.RESET_ALL}\n")
    print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Wordlist & Sözlük Havuzu Yönetimi (Genel & Hedefli Listeler)")
    print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Yapay Zeka Hedefli Liste Üretimi (AI Targeted Wordlist)")
    print(f" {Fore.CYAN}[3]{Style.RESET_ALL} Hibrit Wordlist Birleştirici (Hybrid Wordlist Generation)")
    print(f" {Fore.CYAN}[4]{Style.RESET_ALL} Yerel Hash Denetim Motoru (Local Hash Audit Engine)")
    print(f" {Fore.CYAN}[5]{Style.RESET_ALL} Canlı Login Ekranı Denetimi (Online Login Audit) {Fore.RED}[Sadece Yetkili Hedefler]{Style.RESET_ALL}")
    print(f" {Fore.CYAN}[6]{Style.RESET_ALL} Kıyaslama ve Performans Analizi (Benchmark Module)")
    print(f" {Fore.CYAN}[7]{Style.RESET_ALL} Çıkış (Exit)\n")
    print(f"{Fore.LIGHTBLACK_EX} ⚡ Siber Komutlar: 'targets', 'use <hedef>', 'view 10', 'info', 'search <kelime>', 'help'{Style.RESET_ALL}\n")


def handle_default_wordlist_operations() -> None:
    """[1] Wordlist & Sözlük Havuzu Yönetimi alt menüsü ve operasyonları."""
    while True:
        clear_screen()
        print_banner(version=settings.version)
        print_header("WORDLIST & SÖZLÜK HAVUZU YÖNETİMİ")
        
        default_file = wordlist_manager.default_wordlist_path

        print(f"{Fore.YELLOW}{Style.BRIGHT}--- [A] GENEL / VARSAYILAN SÖZLÜK (Default Wordlist) ---{Style.RESET_ALL}")
        print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Varsayılan Liste Durumu & İstatistikleri ({default_file.name})")
        print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Varsayılan Listeyi Görüntüle (Baştan / Sondan / Aralık / Tümü)")
        print(f" {Fore.CYAN}[3]{Style.RESET_ALL} Wordlist Filtrele & Temizle (Kaynak Seçerek)\n")

        print(f"{Fore.YELLOW}{Style.BRIGHT}--- [B] KİŞİYE ÖZEL AI LİSTELERİ (Targeted & Hybrid Wordlists) ---{Style.RESET_ALL}")
        print(f" {Fore.CYAN}[4]{Style.RESET_ALL} Üretilen Kişiye Özel Listeleri İncele (Baştan / Sondan / Aralık / Tümü)")
        print(f" {Fore.CYAN}[5]{Style.RESET_ALL} Üretilen Özel Listeleri Sil / Temizle (Tekil veya Toplu)\n")

        print(f"{Fore.LIGHTBLACK_EX}--- Diğer ---{Style.RESET_ALL}")
        print(f" {Fore.CYAN}[6]{Style.RESET_ALL} Ana Menüye Dön\n")

        sub_choice = input(f"{Fore.GREEN}{Style.BRIGHT}İşlem Seçiniz [1-6]: {Style.RESET_ALL}").strip()

        if sub_choice == "1":
            try:
                stats = wordlist_manager.get_wordlist_stats(default_file)
                print_header("GENEL WORDLIST İSTATİSTİKLERİ")
                print(f" • Dosya Adı        : {stats['file_name']}")
                print(f" • Toplam Satır     : {stats['total_lines']:,}")
                print(f" • Dosya Boyutu     : {stats['file_size_bytes']:,} bayt")
                print(f" • Min/Max Uzunluk  : {stats['min_length']} / {stats['max_length']} karakter")
                if "metadata" in stats:
                    print(f" • Son İşleme Tarihi: {stats['metadata'].get('created_at', 'N/A')}")
                print_success("İstatistikler başarıyla derlendi.")
            except Exception as e:
                print_error(f"İstatistik alınırken hata oluştu: {e}")
            pause_prompt()

        elif sub_choice == "2":
            try:
                stats = wordlist_manager.get_wordlist_stats(default_file)
                total_lines = stats["total_lines"]

                print_header("VARSAYILAN LİSTE GÖRÜNTÜLEME")
                print(f"{Fore.LIGHTBLACK_EX}Dosyada toplam {total_lines:,} parola bulunuyor.{Style.RESET_ALL}\n")
                print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Baştan N Adet")
                print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Sondan N Adet")
                print(f" {Fore.CYAN}[3]{Style.RESET_ALL} Belirli Aralık (örn: 100-150)")
                print(f" {Fore.CYAN}[4]{Style.RESET_ALL} Tümünü Listele")
                print(f" {Fore.YELLOW}[0]{Style.RESET_ALL} Vazgeç / İptal")

                view_choice = input(f"\n{Fore.GREEN}Seçiminiz [0-4]: {Style.RESET_ALL}").strip()

                results: List[Tuple[int, str]] = []

                if view_choice == "1":
                    n_in = input(f"{Fore.CYAN}Kaç adet gösterilsin? [ENTER = 20]: {Style.RESET_ALL}").strip()
                    n = int(n_in) if n_in.isdigit() and int(n_in) > 0 else 20
                    results = wordlist_manager.get_head(default_file, n=n)

                elif view_choice == "2":
                    n_in = input(f"{Fore.CYAN}Kaç adet gösterilsin? [ENTER = 20]: {Style.RESET_ALL}").strip()
                    n = int(n_in) if n_in.isdigit() and int(n_in) > 0 else 20
                    results = wordlist_manager.get_tail(default_file, n=n)

                elif view_choice == "3":
                    range_in = input(f"{Fore.CYAN}Aralık girin (örn: 100-150): {Style.RESET_ALL}").strip()
                    try:
                        start_s, end_s = range_in.split("-", 1)
                        start_n, end_n = int(start_s.strip()), int(end_s.strip())
                        if start_n < 1 or end_n < start_n:
                            raise ValueError
                        results = wordlist_manager.get_range(default_file, start=start_n, end=end_n)
                    except ValueError:
                        print_error("Geçersiz aralık formatı! Örnek: 100-150")
                        pause_prompt()
                        continue

                elif view_choice == "4":
                    if total_lines > 2000:
                        confirm = input(
                            f"{Fore.RED}DİKKAT: Liste {total_lines:,} satır içeriyor, terminalde tümünü göstermek uzun sürebilir. "
                            f"Devam edilsin mi? [E/h]: {Style.RESET_ALL}"
                        ).strip().lower()
                        if confirm not in ('e', 'evet', 'y', 'yes'):
                            print_info("İşlem kullanıcı tarafından iptal edildi.")
                            pause_prompt()
                            continue
                    results = wordlist_manager.get_range(default_file, start=1, end=None)

                elif view_choice == "0":
                    continue
                else:
                    print_error("Geçersiz seçim!")
                    pause_prompt()
                    continue

                if not results:
                    print_warning("Gösterilecek satır bulunamadı.")
                else:
                    print_header(f"SONUÇLAR ({len(results):,} satır)")
                    for idx, pwd in results:
                        print(f" {Fore.LIGHTBLUE_EX}{idx:06d}.{Style.RESET_ALL} {pwd}")
            except Exception as e:
                print_error(f"Parola listesi okunurken hata: {e}")
            pause_prompt()

        elif sub_choice == "3":
            try:
                print_header("WORDLIST FİLTRELEME SİHİRBAZI")
                print(f"{Fore.LIGHTBLACK_EX}Hedef sistemin parola güvenlik politikasına uygun optimize liste üretin.{Style.RESET_ALL}\n")

                # 0. Kaynak wordlist seçimi
                source_options = [default_file] + sorted(
                    wordlist_manager.generated_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
                )
                print(f"{Fore.CYAN}0. Filtrelenecek Kaynak Wordlist Seçiniz:{Style.RESET_ALL}")
                for i, sf in enumerate(source_options, 1):
                    size_kb = round(sf.stat().st_size / 1024, 2)
                    label = "Varsayılan Liste" if sf == default_file else "Üretilmiş Liste"
                    print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {sf.name} ({label}, {size_kb} KB)")
                src_in = input(f"{Fore.GREEN}Seçiminiz [1-{len(source_options)}, ENTER=1]: {Style.RESET_ALL}").strip()
                src_idx = int(src_in) - 1 if src_in.isdigit() and 1 <= int(src_in) <= len(source_options) else 0
                source_file = source_options[src_idx]

                # 1. Min uzunluk
                default_min = settings.wordlist.min_length
                min_in = input(f"{Fore.CYAN}1. Minimum Parola Uzunluğu [ENTER = {default_min}]: {Style.RESET_ALL}").strip()
                min_val = int(min_in) if min_in.isdigit() and int(min_in) > 0 else default_min

                # 2. Max uzunluk
                default_max = settings.wordlist.max_length
                max_in = input(f"{Fore.CYAN}2. Maksimum Parola Uzunluğu [ENTER = {default_max}]: {Style.RESET_ALL}").strip()
                max_val = int(max_in) if max_in.isdigit() and int(max_in) >= min_val else default_max

                # 3. Karakter kuralı — art arda Evet/Hayır sorularıyla belirlenir
                print(f"\n{Fore.CYAN}3. Parola Karakter Kuralı:{Style.RESET_ALL}")
                print(f"{Fore.LIGHTBLACK_EX}   Aşağıdaki sorulara sırayla E/h cevabı verin.{Style.RESET_ALL}\n")

                def ask_yes_no(question: str) -> bool:
                    ans = input(f"{Fore.CYAN}{question} [e/H]: {Style.RESET_ALL}").strip().lower()
                    return ans in ('e', 'evet', 'y', 'yes')

                if ask_yes_no("Parola SADECE rakamlardan mı oluşsun? (örn: PIN kodu, 123456)"):
                    char_rule = "numeric_only"
                elif ask_yes_no("Parolada en az 1 ÖZEL karakter (!, @, _, . vb.) bulunması şart mı? (örn: pass!123)"):
                    char_rule = "special"
                elif ask_yes_no("Parolada hem HARF hem RAKAM birlikte bulunması şart mı? (örn: admin2024)"):
                    char_rule = "alphanumeric"
                elif ask_yes_no("Parolada en az 1 RAKAM bulunması şart mı? (örn: pass123)"):
                    char_rule = "digit"
                else:
                    char_rule = "all"

                print(f"{Fore.LIGHTBLACK_EX}   -> Seçilen kural: {char_rule}{Style.RESET_ALL}")

                # 4. Büyük / Küçük harf tekilleştirme
                case_in = input(f"\n{Fore.CYAN}4. Büyük/Küçük harf farkı korunsun mu? (Örn: 'Admin' ile 'admin' ayrı tutulsun) [E/h]: {Style.RESET_ALL}").strip().lower()
                case_sens = True if case_in in ('e', 'evet', 'y', 'yes') else False

                # 5. Dosya adı
                default_out_name = f"{source_file.stem}_cleaned_min{min_val}_max{max_val}.txt"
                custom_cl = input(f"\n{Fore.CYAN}5. Kaydedilecek Dosya Adı [ENTER = {default_out_name}]: {Style.RESET_ALL}").strip()
                out_name = custom_cl if custom_cl else default_out_name
                if not out_name.lower().endswith(".txt"):
                    out_name += ".txt"
                output_file = wordlist_manager.generated_dir / out_name

                print_info(f"Filtreleme başlatılıyor (Min: {min_val}, Max: {max_val}, Kural: {char_rule})...")
                
                meta = wordlist_manager.process_and_save(
                    source_path=source_file,
                    output_path=output_file,
                    min_length=min_val,
                    max_length=max_val,
                    case_sensitive=case_sens,
                    char_rule=char_rule
                )
                
                print_success(f"Filtreleme ve tekilleştirme tamamlandı! Dosya: {output_file.name}")
                print(f" • Kaynak Satır     : {meta['total_source_lines']:,}")
                print(f" • Kaydedilen Satır : {meta['unique_written_lines']:,}")
                print(f" • Elenen/Mükerrer  : {meta['filtered_or_duplicate_lines']:,}")
                print(f" • Karakter Kuralı  : {char_rule}")
                print(f" • Çıktı Dosyası    : {output_file.name}")
                print(f" • Metadata Kaydı   : {output_file.name}.metadata.json")
            except Exception as e:
                print_error(f"Filtreleme işlemi sırasında hata: {e}")
            pause_prompt()

        elif sub_choice == "4":
            try:
                gen_files = sorted(list(wordlist_manager.generated_dir.glob("*.txt")), key=lambda p: p.stat().st_mtime, reverse=True)
                if not gen_files:
                    print_warning("Henüz üretilmiş bir özel liste bulunmuyor. Önce Menü [2] veya [3] ile liste üretiniz.")
                    pause_prompt()
                    continue

                print_header("KİŞİYE ÖZEL ÜRETİLEN LİSTELER (wordlists/generated/)")
                for i, gf in enumerate(gen_files, 1):
                    size_kb = round(gf.stat().st_size / 1024, 2)
                    print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {gf.name} ({size_kb} KB)")

                gf_idx = input(f"\n{Fore.GREEN}Görüntülemek istediğiniz dosya no [1-{len(gen_files)}]: {Style.RESET_ALL}").strip()
                try:
                    chosen_gf = gen_files[int(gf_idx) - 1]
                except Exception:
                    print_error("Geçersiz seçim!")
                    pause_prompt()
                    continue

                gf_stats = wordlist_manager.get_wordlist_stats(chosen_gf)
                gf_total = gf_stats["total_lines"]

                print_header(f"İÇERİK ÖNİZLEME: {chosen_gf.name}")
                print(f"{Fore.LIGHTBLACK_EX}Dosyada toplam {gf_total:,} parola bulunuyor.{Style.RESET_ALL}\n")
                print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Baştan N Adet")
                print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Sondan N Adet")
                print(f" {Fore.CYAN}[3]{Style.RESET_ALL} Belirli Aralık (örn: 100-150)")
                print(f" {Fore.CYAN}[4]{Style.RESET_ALL} Tümünü Listele")
                print(f" {Fore.YELLOW}[0]{Style.RESET_ALL} Vazgeç / İptal")

                gf_view_choice = input(f"\n{Fore.GREEN}Seçiminiz [0-4]: {Style.RESET_ALL}").strip()

                gf_results: List[Tuple[int, str]] = []

                if gf_view_choice == "1":
                    n_in = input(f"{Fore.CYAN}Kaç adet gösterilsin? [ENTER = 30]: {Style.RESET_ALL}").strip()
                    n = int(n_in) if n_in.isdigit() and int(n_in) > 0 else 30
                    gf_results = wordlist_manager.get_head(chosen_gf, n=n)

                elif gf_view_choice == "2":
                    n_in = input(f"{Fore.CYAN}Kaç adet gösterilsin? [ENTER = 30]: {Style.RESET_ALL}").strip()
                    n = int(n_in) if n_in.isdigit() and int(n_in) > 0 else 30
                    gf_results = wordlist_manager.get_tail(chosen_gf, n=n)

                elif gf_view_choice == "3":
                    range_in = input(f"{Fore.CYAN}Aralık girin (örn: 100-150): {Style.RESET_ALL}").strip()
                    try:
                        start_s, end_s = range_in.split("-", 1)
                        start_n, end_n = int(start_s.strip()), int(end_s.strip())
                        if start_n < 1 or end_n < start_n:
                            raise ValueError
                        gf_results = wordlist_manager.get_range(chosen_gf, start=start_n, end=end_n)
                    except ValueError:
                        print_error("Geçersiz aralık formatı! Örnek: 100-150")
                        pause_prompt()
                        continue

                elif gf_view_choice == "4":
                    if gf_total > 2000:
                        confirm = input(
                            f"{Fore.RED}DİKKAT: Liste {gf_total:,} satır içeriyor, terminalde tümünü göstermek uzun sürebilir. "
                            f"Devam edilsin mi? [E/h]: {Style.RESET_ALL}"
                        ).strip().lower()
                        if confirm not in ('e', 'evet', 'y', 'yes'):
                            print_info("İşlem kullanıcı tarafından iptal edildi.")
                            pause_prompt()
                            continue
                    gf_results = wordlist_manager.get_range(chosen_gf, start=1, end=None)

                elif gf_view_choice == "0":
                    continue
                else:
                    print_error("Geçersiz seçim!")
                    pause_prompt()
                    continue

                if not gf_results:
                    print_warning("Gösterilecek satır bulunamadı.")
                else:
                    print_header(f"SONUÇLAR ({len(gf_results):,} satır)")
                    for idx, pwd in gf_results:
                        print(f" {Fore.LIGHTBLUE_EX}{idx:06d}.{Style.RESET_ALL} {pwd}")
            except Exception as e:
                print_error(f"Listeler taranırken hata: {e}")
            pause_prompt()

        elif sub_choice == "5":
            try:
                gen_files = sorted(list(wordlist_manager.generated_dir.glob("*.txt")), key=lambda p: p.stat().st_mtime, reverse=True)
                if not gen_files:
                    print_warning("Temizlenecek veya silinecek özel liste bulunmuyor.")
                    pause_prompt()
                    continue

                print_header("ÖZEL WORDLIST SİLME VE TEMİZLEME")
                for i, gf in enumerate(gen_files, 1):
                    size_kb = round(gf.stat().st_size / 1024, 2)
                    print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {gf.name} ({size_kb} KB)")
                print(f" {Fore.RED}[T]{Style.RESET_ALL} Tüm Üretilen Listeleri Temizle (Toplu Sıfırlama)")
                print(f" {Fore.YELLOW}[0]{Style.RESET_ALL} Vazgeç / İptal")

                del_input = input(f"\n{Fore.GREEN}Silmek istediğiniz dosya no veya [T]: {Style.RESET_ALL}").strip().upper()
                if del_input in ("", "0"):
                    continue
                elif del_input == "T":
                    confirm = input(f"{Fore.RED}DİKKAT: Üretilen TÜM listeler silinecektir! Emin misiniz? [E/h]: {Style.RESET_ALL}").strip().lower()
                    if confirm in ('e', 'evet', 'y', 'yes'):
                        deleted_count = 0
                        for f in wordlist_manager.generated_dir.glob("*"):
                            if f.is_file():
                                f.unlink()
                                deleted_count += 1
                        print_success(f"Tüm üretilen listeler temizlendi ({deleted_count} dosya silindi).")
                    else:
                        print_info("İşlem kullanıcı tarafından iptal edildi.")
                elif del_input.isdigit() and 1 <= int(del_input) <= len(gen_files):
                    chosen_del = gen_files[int(del_input) - 1]
                    confirm = input(f"'{chosen_del.name}' kalıcı olarak silinsin mi? [E/h]: ").strip().lower()
                    if confirm in ('e', 'evet', 'y', 'yes'):
                        chosen_del.unlink()
                        meta_f = chosen_del.with_name(f"{chosen_del.name}.metadata.json")
                        if meta_f.exists():
                            meta_f.unlink()
                        print_success(f"'{chosen_del.name}' başarıyla silindi.")
                    else:
                        print_info("İşlem iptal edildi.")
                else:
                    print_error("Geçersiz seçim!")
            except Exception as e:
                print_error(f"Silme işlemi sırasında hata: {e}")
            pause_prompt()

        elif sub_choice == "6":
            break
        else:
            print_error("Lütfen 1-6 arasında geçerli bir seçenek giriniz.")
            pause_prompt()


from ai.provider_gemini import GeminiAIProvider
from core.ranking_engine import RankingEngine
from ai.schemas import TargetProfile, PasswordPolicy


def collect_target_profile_interactively() -> Optional[TargetProfile]:
    """
    Kullanıcıya önce yönlendirici temel soruları soran (hepsi isteğe bağlı, Enter ile geçilebilir),
    ardından serbestçe ek notlar/cümleler yazabileceği metin alanını sunan akış.
    """
    print_header("HEDEF PROFİL BİLGİ GİRİŞİ")
    print(f"{Fore.LIGHTBLACK_EX}İpucu: Soruların hiçbiri zorunlu değildir. Bilmediğiniz kısımları ENTER tuşuna basarak geçebilirsiniz.{Style.RESET_ALL}\n")

    # 1. İsimler
    print(f"{Fore.CYAN}1. Hedef Kişi, Aile Üyeleri veya Evcil Hayvan İsimleri:{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}   Örn: Ahmet, Mehmet, Ayşe, Pamuk, Yılmaz, Kaya (virgülle ayırabilirsiniz){Style.RESET_ALL}")
    names_input = input(f"{Fore.GREEN}   > İsimler: {Style.RESET_ALL}").strip()
    names = [n.strip().capitalize() for n in re.split(r'[,/&+\s]+|\s+ve\s+', names_input) if len(n.strip()) >= 2] if names_input else []

    # 2. Tarihler
    print(f"\n{Fore.CYAN}2. Önemli Tarihler / Doğum / Evlilik Yılları:{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}   Örn: 2004, 2007, 1993, 10.10.2004{Style.RESET_ALL}")
    dates_input = input(f"{Fore.GREEN}   > Tarihler: {Style.RESET_ALL}").strip()
    dates = re.findall(r'\b(?:\d{1,2}[./-]\d{1,2}[./-])?(19\d\d|20[0-2]\d)\b', dates_input) if dates_input else []

    # 3. Konum / Şehir / Plaka
    print(f"\n{Fore.CYAN}3. Yaşanılan Şehir, Memleket veya Plaka Kodu:{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}   Örn: İstanbul, 34, Ankara, 06{Style.RESET_ALL}")
    loc_input = input(f"{Fore.GREEN}   > Şehir/Plaka: {Style.RESET_ALL}").strip()
    locations = [l.strip().capitalize() for l in re.split(r'[,/&+\s]+', loc_input) if l.strip()] if loc_input else []

    # 4. Takım / Hobiler
    print(f"\n{Fore.CYAN}4. Tuttuğu Takım, Hobiler veya İlgi Alanları:{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}   Örn: beşiktaş, fenerbahçe, gitar, kedi{Style.RESET_ALL}")
    interest_input = input(f"{Fore.GREEN}   > Takım/Hobiler: {Style.RESET_ALL}").strip()
    interests = [i.strip().lower() for i in re.split(r'[,/&+\s]+', interest_input) if i.strip()] if interest_input else []

    # 5. Özel Kelimeler / Renk / Lakap
    print(f"\n{Fore.CYAN}5. Özel Kelimeler, Sevdiği Renk veya Lakap:{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}   Örn: mor, mavi, yazılımcı, kartal{Style.RESET_ALL}")
    kw_input = input(f"{Fore.GREEN}   > Özel Kelimeler: {Style.RESET_ALL}").strip()
    keywords = [k.strip().capitalize() for k in re.split(r'[,/&+\s]+', kw_input) if k.strip()] if kw_input else []

    # Aşama 2: Serbest Metin / Ek Notlar Alanı
    print_header("EK HEDEF METNİ / NOTLAR (İsteğe Bağlı)")
    print(f"{Fore.LIGHTBLACK_EX}Yukarıdaki alanlara sığmayan veya serbestçe eklemek istediğiniz cümleleri yazabilirsiniz.")
    print("Örnek: 'annesi öğretmen, köpeğinin cinsi golden, en sevdiği şarkı akdeniz'")
    print(f"Metni yazdıktan sonra ENTER tuşuna basınız (yazmak istemiyorsanız doğrudan ENTER ile geçiniz):{Style.RESET_ALL}")
    free_text = input(f"{Fore.GREEN}   > Ek Notlar / Metin: {Style.RESET_ALL}").strip()

    if free_text:
        print_info("Ek metin doğal dil motoruyla çözümleniyor...")
        provider = GeminiAIProvider()
        parsed_extra = provider.extract_target_profile(free_text)
        # Mevcut verilerle birleştir
        names = sorted(list(set(names + parsed_extra.names)))
        dates = sorted(list(set(dates + parsed_extra.dates)))
        locations = sorted(list(set(locations + parsed_extra.locations)))
        interests = sorted(list(set(interests + parsed_extra.interests)))
        keywords = sorted(list(set(keywords + parsed_extra.keywords)))

    # İlişki çiftleri oluştur
    relations = []
    if len(names) >= 2:
        relations.append([names[0], names[1]])

    profile = TargetProfile(
        names=names,
        dates=dates,
        locations=locations,
        interests=interests,
        relations=relations,
        keywords=keywords
    )

    if profile.is_empty():
        return None

    # Profil özetini ekrana bas
    print_header("OLUŞTURULAN HEDEF PROFİLİ (TargetProfile)")
    print(f" • İsimler        : {', '.join(profile.names) if profile.names else 'Yok'}")
    print(f" • Tarihler       : {', '.join(profile.dates) if profile.dates else 'Yok'}")
    print(f" • Konum / Plaka  : {', '.join(profile.locations) if profile.locations else 'Yok'}")
    print(f" • İlgi Alanları  : {', '.join(profile.interests) if profile.interests else 'Yok'}")
    print(f" • İlişkiler      : {profile.relations if profile.relations else 'Yok'}")
    print(f" • Anahtar Kelime : {', '.join(profile.keywords) if profile.keywords else 'Yok'}")

    return profile


def collect_password_policy_interactively() -> PasswordPolicy:
    """
    Kullanıcıya hedef sistemin parola güvenlik kurallarını sorar (İsteğe bağlı).
    Tüm sorular ENTER tuşuna basılarak varsayılan (esnek) geçilebilir.
    """
    print_header("HEDEF SİSTEM PAROLA POLİTİKASI (İsteğe Bağlı)")
    print(f"{Fore.LIGHTBLACK_EX}Hedef platformun (örn: Instagram, Gmail, Şirket Portalı) parola kurallarını belirtebilirsiniz.")
    print(f"Herhangi bir kural belirtmek istemiyorsanız ENTER tuşuna basarak hızlıca geçebilirsiniz.{Style.RESET_ALL}\n")

    # 1. Min Uzunluk
    min_len_input = input(f"{Fore.CYAN}1. Minimum Karakter Sayısı [Varsayılan: 6, Siteler/Şirketler için genelde 8]: {Style.RESET_ALL}").strip()
    try:
        min_len = int(min_len_input) if min_len_input else 6
    except ValueError:
        min_len = 6

    # 2. Max Uzunluk
    max_len_input = input(f"{Fore.CYAN}2. Maksimum Karakter Sayısı [Varsayılan: 32]: {Style.RESET_ALL}").strip()
    try:
        max_len = int(max_len_input) if max_len_input else 32
    except ValueError:
        max_len = 32

    # 3. Özel Karakter Zorunlu mu?
    req_spec_input = input(f"{Fore.CYAN}3. En az 1 Özel Karakter (!, @, _, . vb.) zorunlu mu? [e/H]: {Style.RESET_ALL}").strip().lower()
    req_special = req_spec_input in ('e', 'evet', 'y', 'yes')

    # 4. Büyük Harf Zorunlu mu?
    req_upper_input = input(f"{Fore.CYAN}4. En az 1 Büyük Harf (A-Z) zorunlu mu? [e/H]: {Style.RESET_ALL}").strip().lower()
    req_upper = req_upper_input in ('e', 'evet', 'y', 'yes')

    # 5. Rakam Zorunlu mu?
    req_digit_input = input(f"{Fore.CYAN}5. En az 1 Rakam (0-9) zorunlu mu? [e/H]: {Style.RESET_ALL}").strip().lower()
    req_digit = req_digit_input in ('e', 'evet', 'y', 'yes')

    policy = PasswordPolicy(
        min_length=min_len,
        max_length=max_len,
        require_special=req_special,
        require_uppercase=req_upper,
        require_digit=req_digit
    )

    print(f"\n{Fore.GREEN}[✓] Uygulanan Parola Politikası: {Fore.WHITE}{policy.summary()}{Style.RESET_ALL}")
    return policy


def save_target_profile_to_disk(profile: TargetProfile) -> Optional[Path]:
    """Kullanıcının girdiği hedef profilini data/synthetic_profiles/ klasörüne kaydeder."""
    import hashlib
    synthetic_dir = BASE_DIR / "data" / "synthetic_profiles"
    synthetic_dir.mkdir(parents=True, exist_ok=True)

    default_name = " ".join(profile.names[:2]) if profile.names else "Yeni Hedef"
    t_name = input(f"\n{Fore.CYAN}Kayıtlı Hedef Adı / Açıklaması [ENTER = {default_name}]: {Style.RESET_ALL}").strip() or default_name

    slug = re.sub(r'[^a-zA-Z0-9_]', '_', t_name.lower()).strip('_') or "target"
    slug_file = synthetic_dir / f"target_{slug}.json"

    print(f"{Fore.LIGHTBLACK_EX}İpucu: Benchmark veya hash testlerinde kullanılacak doğru test parolasını (Ground Truth) belirtebilirsiniz.{Style.RESET_ALL}")
    pwd_hint = input(f"{Fore.CYAN}Test parolası (Ground Truth) [Boş bırakılabilir]: {Style.RESET_ALL}").strip()
    target_hash = ""
    if pwd_hint:
        target_hash = hashlib.sha256(pwd_hint.encode("utf-8")).hexdigest()

    data = {
        "target_id": f"target_{slug}",
        "target_name": t_name,
        "profile": profile.to_detailed_dict(),
        "ground_truth": {
            "plain_password_hint": pwd_hint or f"{t_name} hedef profili",
            "hash_type": "sha256",
            "target_hash": target_hash
        }
    }

    with open(slug_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print_success(f"Hedef profil başarıyla kaydedildi: data/synthetic_profiles/{slug_file.name}")
    print_info("Bu hedef artık [4] Hash Denetim Motoru ve [6] Kıyaslama Modülü hedefleri arasında seçilebilir!")
    return slug_file


def handle_targeted_wordlist_generation() -> None:
    """[2] AI Targeted Wordlist Generation operasyonu."""
    clear_screen()
    print_banner(version=settings.version)
    print_header("[2] YAPAY ZEKA HEDEFLİ LİSTE ÜRETİMİ (AI Targeted Wordlist)")

    profile = collect_target_profile_interactively()
    if not profile or profile.is_empty():
        print_warning("Hedef profil oluşturulamadı veya işlem iptal edildi.")
        pause_prompt()
        return

    # Hedef sistem parola politikasını al (İsteğe bağlı)
    policy = collect_password_policy_interactively()

    # Dosya adını belirle
    target_slug = profile.names[0].lower() if profile.names else "target"
    default_filename = f"ai_targeted_{target_slug}.txt"

    print_header("KAYIT VE DOSYA ADI YAPILANDIRMASI")
    print(f"{Fore.LIGHTBLACK_EX}Üretilen liste 'wordlists/generated/' dizinine kaydedilecektir.{Style.RESET_ALL}")
    custom_name = input(f"{Fore.CYAN}Kaydedilecek Wordlist dosya adı [ENTER = {default_filename}]: {Style.RESET_ALL}").strip()
    if custom_name:
        chosen_filename = custom_name if custom_name.lower().endswith(".txt") else f"{custom_name}.txt"
    else:
        chosen_filename = default_filename

    confirm = input(f"\n{Fore.YELLOW}'{chosen_filename}' adıyla parola listesi üretilsin mi? [E/h]: {Style.RESET_ALL}").strip().lower()
    if confirm in ('h', 'hayir', 'n', 'no'):
        print_info("İşlem kullanıcı tarafından iptal edildi.")
        pause_prompt()
        return

    try:
        print_info("Akıllı kural motoru, parola filtresi ve skorlama çalışıyor...")
        engine = RankingEngine(profile, policy=policy)
        output_file, meta = engine.build_targeted_wordlist(output_filename=chosen_filename)

        print_success("Yapay Zeka Hedefli Wordlist Başarıyla Üretildi ve Kaydedildi!")
        print(f" • Dosya Adı        : {Fore.GREEN}{Style.BRIGHT}{output_file.name}{Style.RESET_ALL}")
        print(f" • Tam Dosya Yolu   : {output_file}")
        print(f" • Parola Politikası: {meta.get('password_policy', 'Varsayılan')}")
        print(f" • Toplam Aday      : {meta['total_candidates']:,}")
        print(f" • Priority 1 (Yüksek Öncelik): {meta['priority_distribution']['priority_1_high']:,}")
        print(f" • Priority 2 (Orta Öncelik)  : {meta['priority_distribution']['priority_2_medium']:,}")
        print(f" • Priority 3 (Düşük/Leet)    : {meta['priority_distribution']['priority_3_low']:,}")
        print(f" • Geçen Süre       : {meta['duration_seconds']} sn")
        print(f" • Metadata         : {output_file.name}.metadata.json")

        save_target_profile_to_disk(profile)

    except Exception as e:
        logger.exception(f"Hedefli wordlist üretim hatası: {e}")
        print_error(f"Üretim sırasında hata oluştu: {e}")

    pause_prompt()


def handle_hybrid_wordlist_generation() -> None:
    """[3] Hybrid Wordlist Generation operasyonu: mevcut wordlist dosyalarını seçip birleştirir."""
    clear_screen()
    print_banner(version=settings.version)
    print_header("[3] HİBRİT WORDLIST BİRLEŞTİRİCİ (Hybrid Wordlist Generation)")
    print(f"{Fore.LIGHTBLACK_EX}Var olan wordlist dosyalarından 2 veya daha fazlasını seçip tek bir listede birleştirin.{Style.RESET_ALL}\n")

    source_options = [wordlist_manager.default_wordlist_path] + sorted(
        wordlist_manager.generated_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if len(source_options) < 2:
        print_warning("Birleştirmek için en az 2 wordlist gerekiyor. Önce Menü [1] veya [2] ile ek liste üretiniz.")
        pause_prompt()
        return

    for i, sf in enumerate(source_options, 1):
        size_kb = round(sf.stat().st_size / 1024, 2)
        label = "Varsayılan Liste" if sf == wordlist_manager.default_wordlist_path else "Üretilmiş Liste"
        print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {sf.name} ({label}, {size_kb} KB)")

    sel_in = input(f"\n{Fore.GREEN}Birleştirilecek dosyaların numaralarını girin (örn: 1,3,4): {Style.RESET_ALL}").strip()
    try:
        indices = sorted(set(int(x.strip()) for x in sel_in.split(",") if x.strip()))
        if len(indices) < 2 or any(i < 1 or i > len(source_options) for i in indices):
            raise ValueError
        chosen_sources = [source_options[i - 1] for i in indices]
    except ValueError:
        print_error("Geçersiz seçim! En az 2 geçerli dosya numarası virgülle ayırarak giriniz (örn: 1,2).")
        pause_prompt()
        return

    case_in = input(f"\n{Fore.CYAN}Büyük/Küçük harf farkı korunsun mu? (Örn: 'Admin' ile 'admin' ayrı tutulsun) [e/H]: {Style.RESET_ALL}").strip().lower()
    case_sens = case_in in ('e', 'evet', 'y', 'yes')

    default_filename = "hybrid_" + "_".join(p.stem for p in chosen_sources)[:60] + ".txt"

    print_header("KAYIT VE DOSYA ADI YAPILANDIRMASI")
    print(f"{Fore.LIGHTBLACK_EX}Üretilen hibrit liste 'wordlists/generated/' dizinine kaydedilecektir.{Style.RESET_ALL}")
    custom_name = input(f"{Fore.CYAN}Kaydedilecek Hibrit Wordlist dosya adı [ENTER = {default_filename}]: {Style.RESET_ALL}").strip()
    if custom_name:
        chosen_filename = custom_name if custom_name.lower().endswith(".txt") else f"{custom_name}.txt"
    else:
        chosen_filename = default_filename
    output_file = wordlist_manager.generated_dir / chosen_filename

    try:
        print_info(f"{len(chosen_sources)} dosya birleştiriliyor ve tekilleştiriliyor...")
        meta = wordlist_manager.merge_wordlists(
            source_paths=chosen_sources,
            output_path=output_file,
            case_sensitive=case_sens
        )

        print_success("Hibrit Wordlist Başarıyla Birleştirildi ve Kaydedildi!")
        print(f" • Dosya Adı        : {Fore.GREEN}{Style.BRIGHT}{output_file.name}{Style.RESET_ALL}")
        print(f" • Tam Dosya Yolu   : {output_file}")
        print(f" • Kaynak Dosyalar  : {', '.join(meta['source_files'])}")
        print(f" • Toplam Kaynak Satır : {meta['total_source_lines']:,}")
        print(f" • Kaydedilen Benzersiz: {meta['unique_written_lines']:,}")
        print(f" • Elenen/Mükerrer     : {meta['filtered_or_duplicate_lines']:,}")
        print(f" • Metadata         : {output_file.name}.metadata.json")

    except Exception as e:
        logger.exception(f"Hibrit liste birleştirme hatası: {e}")
        print_error(f"Birleştirme sırasında hata: {e}")

    pause_prompt()


from core.hash_audit_engine import test_engine, LocalHashAuditEngine
import json


def _select_audit_target() -> Optional[Tuple[str, str]]:
    """Denetim hedefini (hash + açıklama) kullanıcıdan alır. İptalde None döner."""
    print_header("[4] YEREL HASH DENETİM MOTORU (Local Hash Audit Engine)")

    print("Denetim için hedef kaynağı seçiniz:")
    print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Kayıtlı Hedef Profilinden Yükle (data/synthetic_profiles/)")
    print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Manuel Hedef Gir (SHA-256 Hash veya Açık Parola)")
    print(f" {Fore.YELLOW}[0]{Style.RESET_ALL} Ana Menüye Dön\n")

    sub_choice = input(f"{Fore.GREEN}{Style.BRIGHT}Seçiminiz [0-2]: {Style.RESET_ALL}").strip()

    if sub_choice == "1":
        profiles_dir = BASE_DIR / "data" / "synthetic_profiles"
        profile_files = list(profiles_dir.glob("*.json"))
        if not profile_files:
            print_error("Kayıtlı hedef profili bulunamadı! Önce Menü [2] ile bir hedef profili üretip kaydediniz.")
            return None

        print_header("KAYITLI HEDEF PROFİLLERİ")
        for i, pf in enumerate(profile_files, 1):
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                gt = data.get("ground_truth", {})
                has_hash = bool(gt.get("target_hash"))
                hash_info = f"Hash: {gt['target_hash'][:12]}..." if has_hash else f"{Fore.YELLOW}Hash yok (test parolası girilmemiş){Style.RESET_ALL}"
                print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {data.get('target_name', pf.stem)} ({hash_info})")
            except Exception:
                print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {pf.stem} ({Fore.RED}profil okunamadı{Style.RESET_ALL})")

        idx_str = input(f"\n{Fore.GREEN}Profil Numarası Seçiniz [1-{len(profile_files)}, ENTER=iptal]: {Style.RESET_ALL}").strip()
        if not idx_str:
            return None
        try:
            chosen = profile_files[int(idx_str) - 1]
            with open(chosen, "r", encoding="utf-8") as f:
                data = json.load(f)
            target_hash = data["ground_truth"]["target_hash"]
            if not target_hash:
                print_error("Bu profilin kayıtlı bir test parolası/hash'i yok. Lütfen [2] ile manuel hash girin.")
                return None
            target_description = f"{data.get('target_name')} ({data['ground_truth'].get('plain_password_hint')})"
            return target_hash, target_description
        except Exception:
            print_error("Geçersiz seçim!")
            return None

    elif sub_choice == "2":
        user_in = input(f"\n{Fore.GREEN}Hedef SHA-256 Hash veya Açık Parola giriniz: {Style.RESET_ALL}").strip()
        if not user_in:
            return None
        if len(user_in) == 64 and all(c in "0123456789abcdefABCDEF" for c in user_in):
            target_hash = user_in.lower()
            target_description = f"Manuel Hash ({target_hash[:10]}...)"
        else:
            target_hash = LocalHashAuditEngine.compute_hash_sha256(user_in)
            target_description = f"Manuel Parola ('{user_in}' -> {target_hash[:10]}...)"
        return target_hash, target_description

    elif sub_choice == "0" or not sub_choice:
        return None
    else:
        print_error("Geçersiz seçenek.")
        return None


def _select_audit_wordlist() -> Optional[Path]:
    """Denetimde kullanılacak wordlist dosyasını kullanıcıdan alır. İptalde None döner."""
    print_header("KULLANILACAK WORDLIST SEÇİMİ")
    available_wordlists = []
    default_wl = BASE_DIR / "wordlists" / "default.txt"
    if default_wl.is_file():
        available_wordlists.append(default_wl)
    gen_dir = BASE_DIR / "wordlists" / "generated"
    if gen_dir.is_dir():
        available_wordlists.extend(sorted(gen_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True))

    if not available_wordlists:
        print_error("Kullanılabilir wordlist bulunamadı! Önce Menü [1], [2] veya [3] ile liste üretiniz.")
        return None

    for i, wl in enumerate(available_wordlists, 1):
        try:
            total_lines = wordlist_manager.get_wordlist_stats(wl)["total_lines"]
            count_info = f"{total_lines:,} parola"
        except Exception:
            count_info = f"{round(wl.stat().st_size / 1024, 1)} KB"
        label = "Varsayılan Liste" if wl == default_wl else "Üretilmiş Liste"
        print(f" {Fore.CYAN}[{i}]{Style.RESET_ALL} {wl.name} ({label}, {count_info})")
    print(f" {Fore.YELLOW}[0]{Style.RESET_ALL} Vazgeç / Geri")

    wl_choice = input(f"\n{Fore.GREEN}Wordlist Seçiniz [0-{len(available_wordlists)}]: {Style.RESET_ALL}").strip()
    if wl_choice == "0" or not wl_choice:
        return None
    try:
        return available_wordlists[int(wl_choice) - 1]
    except Exception:
        print_error("Geçersiz wordlist seçimi!")
        return None


def handle_local_hash_audit_engine() -> None:
    """[4] Yerel Hash Denetim Motoru operasyonu."""
    clear_screen()
    print_banner(version=settings.version)

    target = _select_audit_target()
    if target is None:
        pause_prompt()
        return
    target_hash, target_description = target

    while True:
        chosen_wl = _select_audit_wordlist()
        if chosen_wl is None:
            break

        print_info(f"Denetim başlatılıyor...\nHedef: {target_description}\nListe: {chosen_wl.name}")
        result = test_engine.audit_wordlist_stream(
            target_hash=target_hash,
            wordlist_path=chosen_wl
        )

        print_header("DENETİM SONUÇ RAPORU")
        if result.matched:
            print_success("PAROLA BAŞARIYLA TESPİT EDİLDİ (MATCH)!")
            print(f" • Açık Parola       : {Fore.YELLOW}{Style.BRIGHT}{result.matched_password}{Style.RESET_ALL}")
            print(f" • Bulunduğu Sıra    : {Fore.GREEN}{result.position:,}. denemede{Style.RESET_ALL}")
            print(f" • Test Edilen Aday  : {result.total_tested:,}")
            print(f" • Geçen Süre        : {result.duration_seconds} saniye")
            print(f" • Ortalama Hız      : {result.hashes_per_second:,.0f} hash/sn")
        else:
            print_error("EŞLEŞME BULUNAMADI!")
            print(f" • Test Edilen Aday  : {result.total_tested:,}")
            print(f" • Geçen Süre        : {result.duration_seconds} saniye")
            print(f" • Ortalama Hız      : {result.hashes_per_second:,.0f} hash/sn")
            print_info("İpucu: Hedefe yönelik AI Wordlist (Menü [2]) üreterek tekrar deneyebilirsiniz.")

        again = input(f"\n{Fore.CYAN}Aynı hedefi başka bir wordlist ile tekrar denemek ister misiniz? [e/H]: {Style.RESET_ALL}").strip().lower()
        if again not in ('e', 'evet', 'y', 'yes'):
            break

    pause_prompt()


from core.safety_controller import (
    SafetyController,
    MockAuthService,
    run_safety_monitored_audit,
    SafetyTriggerReason
)
from core.benchmark import BenchmarkSuite
from core.online_login_auditor import HttpLoginAuditService


def handle_safety_controller_audit() -> None:
    """[5] Güvenlik Denetleyicisi ve Mock Audit alt menüsü."""
    clear_screen()
    print_banner(version=settings.version)
    print_header("GÜVENLİK DENETLEYİCİSİ VE MOCK AUDIT (Safety Controller)")
    print(f"{Fore.YELLOW}{Style.BRIGHT} [!] ETİK VE GÜVENLİK İLKESİ:{Style.RESET_ALL}")
    print(" Cybzenor, hedef sistemlerin rate-limit veya hesap kilitleme mekanizmalarını asla aşmaya çalışmaz.")
    print(" Anormal yanıt veya engelleme sinyali tespit ettiği anda testi derhal güvenli biçimde durdurur.\n")

    print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Senaryo A: Rate-Limit Simülasyonu (HTTP 429 Too Many Requests)")
    print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Senaryo B: Hesap Kilitleme Simülasyonu (Account Lockout / 423 Locked)")
    print(f" {Fore.CYAN}[3]{Style.RESET_ALL} Senaryo C: CAPTCHA / Bot Doğrulama Tespiti")
    print(f" {Fore.CYAN}[4]{Style.RESET_ALL} Senaryo D: Maksimum Ardışık Başarısızlık Eşiği Aşımı ({settings.safety.max_consecutive_failures} Deneme)")
    print(f" {Fore.CYAN}[5]{Style.RESET_ALL} Senaryo E: Güvenli Eşleşme (Limitler aşılmadan doğru parola tespiti)")
    print(f" {Fore.CYAN}[6]{Style.RESET_ALL} Ana Menüye Dön\n")

    scenario = input(f"{Fore.GREEN}Senaryo seçiniz [1-6]: {Style.RESET_ALL}").strip()
    if scenario == "6" or not scenario:
        return

    # Kullanılacak wordlist
    wl_path = wordlist_manager.default_wordlist_path
    if not wl_path.is_file():
        print_error(f"Test için wordlist bulunamadı: {wl_path}")
        pause_prompt()
        return

    print_info("Mock Güvenlik Testi başlatılıyor...")

    if scenario == "1":
        # 15 denemeden sonra HTTP 429
        mock_svc = MockAuthService(target_password="NON_EXISTENT_PWD", rate_limit_after=15, delay_ms=15)
        print_info("Senaryo A seçildi: 15 denemeden sonra hedef servis HTTP 429 döndürecek.")
    elif scenario == "2":
        # 10 başarısızlıktan sonra hesap kilidi
        mock_svc = MockAuthService(target_password="NON_EXISTENT_PWD", lockout_after_failures=10, delay_ms=15)
        print_info("Senaryo B seçildi: 10 hatalı denemeden sonra servis 'Account Locked' yanıtı verecek.")
    elif scenario == "3":
        # 12 denemeden sonra CAPTCHA
        mock_svc = MockAuthService(target_password="NON_EXISTENT_PWD", captcha_after=12, delay_ms=15)
        print_info("Senaryo C seçildi: 12 denemeden sonra servis 'Please solve the CAPTCHA' döndürecek.")
    elif scenario == "4":
        # Sınır aşımı
        mock_svc = MockAuthService(target_password="NON_EXISTENT_PWD", delay_ms=5)
        print_info(f"Senaryo D seçildi: {settings.safety.max_consecutive_failures} ardışık başarısızlıktan sonra denetim durdurulacak.")
    elif scenario == "5":
        # İlk satırlarda doğru parola
        mock_svc = MockAuthService(target_password="password", rate_limit_after=50, delay_ms=15)
        print_info("Senaryo E seçildi: 'password' kelimesi tespit edilecek.")
    else:
        print_error("Geçersiz seçim.")
        pause_prompt()
        return

    report = run_safety_monitored_audit(wordlist_path=wl_path, mock_service=mock_svc)

    print_header("GÜVENLİK TESTİ SONUÇ RAPORU")
    if "SAFETY_HALTED" in report["status"]:
        print(f"{Fore.RED}{Style.BRIGHT}[!] TEST GÜVENLİK PROTOKOLÜ GEREĞİ DURDURULDU:{Style.RESET_ALL}")
        print(f" • Durum              : {Fore.YELLOW}{report['status']}{Style.RESET_ALL}")
        print(f" • Açıklama           : {report['error_message']}")
        print(f" • Yapılan Deneme     : {report['attempts_made']}")
        print(f" • Ardışık Hata Sayısı: {report['consecutive_failures']}")
        print(f" • Geçen Süre         : {report['elapsed_seconds']} sn")
        print_success("Güvenlik Denetleyicisi etik sınırları koruyarak hedefi koruma altına aldı.")
    elif report["status"] == "MATCH_FOUND":
        print_success("PAROLA GÜVENLİ VE BAŞARILI BİR ŞEKİLDE BULUNDU!")
        print(f" • Eşleşen Parola     : {Fore.YELLOW}{Style.BRIGHT}{report['matched_password']}{Style.RESET_ALL}")
        print(f" • Deneme Sayısı      : {report['attempts_made']}")
        print(f" • Geçen Süre         : {report['elapsed_seconds']} sn")
    else:
        print_info(f"Test tamamlandı: {report['status']}")

    pause_prompt()


def handle_online_login_audit() -> None:
    """[5] Canlı Login Ekranı Denetimi: gerçek bir HTTP login formuna karşı SafetyController gözetiminde parola denemesi yapar."""
    clear_screen()
    print_banner(version=settings.version)
    print_header("[5] CANLI LOGIN EKRANI DENETİMİ (Online Login Audit)")

    print(f"{Fore.RED}{Style.BRIGHT}[!] YASAL UYARI:{Style.RESET_ALL}")
    print(f"{Fore.RED}Bu özellik GERÇEK bir sisteme ağ üzerinden istek gönderir.{Style.RESET_ALL}")
    print(f"{Fore.RED}Sadece kendi sisteminizde veya yazılı izinle yetkilendirildiğiniz hedeflerde kullanınız.{Style.RESET_ALL}")
    print(f"{Fore.RED}Yetkisiz kullanım suçtur ve tüm sorumluluk kullanıcıya aittir.{Style.RESET_ALL}\n")

    confirm = input(f"{Fore.YELLOW}Bu hedefte test yapma yetkiniz olduğunu onaylıyor musunuz? [E/h]: {Style.RESET_ALL}").strip().lower()
    if confirm not in ('e', 'evet', 'y', 'yes'):
        print_info("İşlem kullanıcı tarafından iptal edildi.")
        pause_prompt()
        return

    print_header("HEDEF LOGIN FORMU YAPILANDIRMASI")

    target_url = input(f"{Fore.CYAN}1. Hedef Login URL'si (örn: http://localhost:8080/login): {Style.RESET_ALL}").strip()
    if not target_url:
        print_error("Hedef URL boş olamaz!")
        pause_prompt()
        return

    method_in = input(f"{Fore.CYAN}2. HTTP Metodu [ENTER = POST]: {Style.RESET_ALL}").strip().upper()
    method = method_in if method_in in ("POST", "GET") else "POST"

    content_type = "form"
    if method == "POST":
        ct_in = input(f"{Fore.CYAN}3. İçerik Tipi - form ya da json [ENTER = form]: {Style.RESET_ALL}").strip().lower()
        content_type = "json" if ct_in == "json" else "form"

    username_field = input(f"{Fore.CYAN}4. Kullanıcı Adı Alan İsmi [ENTER = username]: {Style.RESET_ALL}").strip() or "username"
    username_value = input(f"{Fore.CYAN}5. Denenecek Kullanıcı Adı: {Style.RESET_ALL}").strip()
    if not username_value:
        print_error("Kullanıcı adı boş olamaz!")
        pause_prompt()
        return
    password_field = input(f"{Fore.CYAN}6. Parola Alan İsmi [ENTER = password]: {Style.RESET_ALL}").strip() or "password"

    print(f"\n{Fore.CYAN}7. Başarı Nasıl Tespit Edilsin?{Style.RESET_ALL}")
    print(f" {Fore.CYAN}[1]{Style.RESET_ALL} Yanıt metninde bir BAŞARI belirteci ara (örn: 'Hoş geldiniz', 'Dashboard')")
    print(f" {Fore.CYAN}[2]{Style.RESET_ALL} Yanıt metninde bir HATA belirteci ara (yokluğu = başarı) (örn: 'Hatalı parola', 'Invalid')")
    print(f" {Fore.CYAN}[3]{Style.RESET_ALL} Sadece HTTP status koduna bak (200/301/302/303 = başarı)")
    detect_choice = input(f"{Fore.GREEN}Seçiminiz [1-3, ENTER=3]: {Style.RESET_ALL}").strip()

    success_indicator = None
    failure_indicator = None
    if detect_choice == "1":
        success_indicator = input(f"{Fore.CYAN}   Başarı belirteci metni: {Style.RESET_ALL}").strip()
    elif detect_choice == "2":
        failure_indicator = input(f"{Fore.CYAN}   Hata belirteci metni: {Style.RESET_ALL}").strip()

    csrf_field = None
    csrf_regex = None
    csrf_in = input(f"\n{Fore.CYAN}8. Form bir CSRF token gerektiriyor mu? [e/H]: {Style.RESET_ALL}").strip().lower()
    if csrf_in in ('e', 'evet', 'y', 'yes'):
        csrf_field = input(f"{Fore.CYAN}   CSRF alan ismi (örn: csrf_token): {Style.RESET_ALL}").strip() or None
        csrf_regex = input(f"{Fore.CYAN}   Token'ı yakalayacak regex (1 grup, örn: name=\"csrf_token\" value=\"(.*?)\"): {Style.RESET_ALL}").strip() or None

    delay_in = input(f"\n{Fore.CYAN}9. İstekler arası bekleme (ms) [ENTER = {settings.safety.online_request_delay_ms}]: {Style.RESET_ALL}").strip()
    request_delay_ms = int(delay_in) if delay_in.isdigit() else None

    # Wordlist seçimi (aynı seçici Hash Denetim Motoru ile paylaşılıyor)
    chosen_wl = _select_audit_wordlist()
    if chosen_wl is None:
        pause_prompt()
        return

    print_header("DENETİM ÖZETİ")
    print(f" • Hedef URL        : {target_url}")
    print(f" • Metod            : {method} ({content_type})")
    print(f" • Kullanıcı Adı    : {username_value}")
    print(f" • Wordlist         : {chosen_wl.name}")
    print(f" • Güvenlik Eşiği   : {settings.safety.max_consecutive_failures} ardışık başarısızlık")
    final_confirm = input(f"\n{Fore.YELLOW}Denetim başlatılsın mı? [E/h]: {Style.RESET_ALL}").strip().lower()
    if final_confirm not in ('e', 'evet', 'y', 'yes'):
        print_info("İşlem kullanıcı tarafından iptal edildi.")
        pause_prompt()
        return

    try:
        service = HttpLoginAuditService(
            target_url=target_url,
            username_field=username_field,
            username_value=username_value,
            password_field=password_field,
            method=method,
            content_type=content_type,
            success_indicator=success_indicator,
            failure_indicator=failure_indicator,
            csrf_field=csrf_field,
            csrf_regex=csrf_regex,
            request_delay_ms=request_delay_ms,
        )

        print_info("Canlı denetim başlatılıyor (SafetyController gözetiminde)...")
        report = run_safety_monitored_audit(
            wordlist_path=chosen_wl,
            mock_service=service,
            safety_controller=SafetyController()
        )

        print_header("CANLI LOGIN DENETİM SONUÇ RAPORU")
        if report["status"] == "MATCH_FOUND":
            print_success("PAROLA BAŞARIYLA TESPİT EDİLDİ (MATCH)!")
            print(f" • Açık Parola       : {Fore.YELLOW}{Style.BRIGHT}{report['matched_password']}{Style.RESET_ALL}")
            print(f" • Deneme Sayısı     : {report['attempts_made']:,}")
            print(f" • Geçen Süre        : {report['elapsed_seconds']} saniye")
        elif report["status"].startswith("SAFETY_HALTED"):
            print_warning("TEST GÜVENLİK PROTOKOLÜ GEREĞİ DURDURULDU:")
            print(f" • Durum             : {report['status']}")
            print(f" • Açıklama          : {report['error_message']}")
            print(f" • Yapılan Deneme    : {report['attempts_made']:,}")
            print(f" • Geçen Süre        : {report['elapsed_seconds']} saniye")
            print_success("Güvenlik Denetleyicisi etik sınırları koruyarak hedefi koruma altına aldı.")
        else:
            print_error("EŞLEŞME BULUNAMADI!")
            print(f" • Deneme Sayısı     : {report['attempts_made']:,}")
            print(f" • Geçen Süre        : {report['elapsed_seconds']} saniye")

    except Exception as e:
        logger.exception(f"Canlı login denetimi hatası: {e}")
        print_error(f"Denetim sırasında hata oluştu: {e}")

    pause_prompt()


def handle_benchmark_module() -> None:
    """[6] Kıyaslama ve Performans Analizi (Benchmark Module)."""
    clear_screen()
    print_banner(version=settings.version)
    print_header("KIYASLAMA VE BAŞARI ANALİZİ (Benchmark Module)")
    print(f"{Fore.LIGHTBLACK_EX}Üç farklı wordlist (Default, AI Targeted, Hybrid) aynı hedef üzerinde yarıştırılır.{Style.RESET_ALL}\n")

    # Sentetik hedefleri listele
    synthetic_dir = BASE_DIR / "data" / "synthetic_profiles"
    synthetic_files = list(synthetic_dir.glob("*.json")) if synthetic_dir.exists() else []

    target_hash = None
    target_label = None
    sdata: Dict[str, Any] = {}

    if synthetic_files:
        print(f"{Fore.YELLOW}Kayıtlı Sentetik Hedefler:{Style.RESET_ALL}")
        for idx, sfile in enumerate(synthetic_files, 1):
            try:
                with open(sfile, "r", encoding="utf-8") as f:
                    sdata = json.load(f)
                pname = sdata.get("target_name") or sdata.get("target_id", sfile.stem)
                gt = sdata.get("ground_truth", {}) if isinstance(sdata.get("ground_truth"), dict) else {}
                pw = gt.get("plain_password_hint") or sdata.get("ground_truth_password", "Bilinmiyor")
                print(f" {Fore.CYAN}[{idx}]{Style.RESET_ALL} {pname} (Ground Truth: {pw})")
            except Exception:
                print(f" {Fore.CYAN}[{idx}]{Style.RESET_ALL} {sfile.name}")
        print(f" {Fore.CYAN}[{len(synthetic_files) + 1}]{Style.RESET_ALL} Manuel SHA-256 Hash veya Açık Parola Gir")
        print(f" {Fore.CYAN}[{len(synthetic_files) + 2}]{Style.RESET_ALL} İptal / Ana Menü")

        choice = input(f"\n{Fore.GREEN}Hedef seçiniz [1-{len(synthetic_files) + 2}]: {Style.RESET_ALL}").strip()
        if choice == str(len(synthetic_files) + 2) or not choice:
            return

        if choice.isdigit() and 1 <= int(choice) <= len(synthetic_files):
            chosen_file = synthetic_files[int(choice) - 1]
            with open(chosen_file, "r", encoding="utf-8") as f:
                sdata = json.load(f)
            gt = sdata.get("ground_truth", {}) if isinstance(sdata.get("ground_truth"), dict) else {}
            target_hash = gt.get("target_hash") or sdata.get("sha256_hash")
            target_label = sdata.get("target_name") or sdata.get("target_id", chosen_file.stem)
        elif choice == str(len(synthetic_files) + 1):
            user_in = input(f"{Fore.GREEN}Hedef SHA-256 Hash veya Parola: {Style.RESET_ALL}").strip()
            if not user_in:
                return
            if len(user_in) == 64 and all(c in "0123456789abcdefABCDEF" for c in user_in):
                target_hash = user_in.lower()
            else:
                target_hash = LocalHashAuditEngine.compute_hash_sha256(user_in)
            target_label = "Manuel Hedef"
            sdata = {}
    else:
        user_in = input(f"{Fore.GREEN}Hedef SHA-256 Hash veya Açık Parola girin: {Style.RESET_ALL}").strip()
        if not user_in:
            return
        if len(user_in) == 64 and all(c in "0123456789abcdefABCDEF" for c in user_in):
            target_hash = user_in.lower()
        else:
            target_hash = LocalHashAuditEngine.compute_hash_sha256(user_in)
        target_label = "Manuel Hedef"
        sdata = {}

    # Wordlist yollarını belirle
    default_path = wordlist_manager.default_wordlist_path
    generated_dir = BASE_DIR / "wordlists" / "generated"

    # wordlists/generated altındaki tüm txt dosyalarını topla
    all_gen_files = sorted([f for f in generated_dir.glob("*.txt") if f.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)

    targeted_path = None
    hybrid_path = None

    if all_gen_files:
        print(f"\n{Fore.YELLOW}Kıyaslamada Yarıştırılacak Hedefli Wordlist:{Style.RESET_ALL}")
        for idx, gf in enumerate(all_gen_files, 1):
            print(f" {Fore.CYAN}[{idx}]{Style.RESET_ALL} {gf.name} ({round(gf.stat().st_size / 1024, 1)} KB)")
        print(f" {Fore.CYAN}[A]{Style.RESET_ALL} Otomatik Eşleştir (En son üretilen liste)")

        wl_choice = input(f"{Fore.GREEN}Seçiminiz [1-{len(all_gen_files)} veya A]: {Style.RESET_ALL}").strip().upper()
        if wl_choice.isdigit() and 1 <= int(wl_choice) <= len(all_gen_files):
            targeted_path = all_gen_files[int(wl_choice) - 1]

    if not targeted_path:
        targeted_files = sorted(generated_dir.glob("ai_targeted_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if targeted_files:
            targeted_path = targeted_files[0]
        elif all_gen_files:
            targeted_path = all_gen_files[0]
        elif "profile" in sdata:
            print_info(f"'{target_label}' için AI Hedefli Wordlist otomatik üretiliyor...")
            from ai.schemas import TargetProfile
            from core.ranking_engine import RankingEngine
            prof_obj = TargetProfile(**sdata["profile"])
            r_engine = RankingEngine(prof_obj)
            auto_target_path, _ = r_engine.build_targeted_wordlist()
            targeted_path = auto_target_path

    # Hibrit liste tespiti
    hybrid_files = sorted(generated_dir.glob("hybrid_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if hybrid_files:
        hybrid_path = hybrid_files[0]
    elif targeted_path and "profile" in sdata:
        print_info("Hibrit Wordlist otomatik birleştiriliyor...")
        from ai.schemas import TargetProfile
        from core.ranking_engine import RankingEngine
        h_engine = RankingEngine(TargetProfile(**sdata["profile"]))
        auto_hybrid_path, _ = h_engine.build_hybrid_wordlist()
        hybrid_path = auto_hybrid_path

    targeted_path = targeted_path or default_path
    hybrid_path = hybrid_path or default_path

    print(f"\n{Fore.LIGHTBLACK_EX}--- Kıyaslanacak Wordlist'ler ---")
    print(f" 1. Varsayılan: {default_path.name}")
    print(f" 2. AI Hedefli : {targeted_path.name}")
    print(f" 3. Hibrit     : {hybrid_path.name}")
    print(f"--------------------------------{Style.RESET_ALL}\n")

    print_info("Benchmark yarışı başlatılıyor...")
    suite = BenchmarkSuite()
    report = suite.run_comparative_benchmark(
        target_hash=target_hash,
        default_path=default_path,
        targeted_path=targeted_path,
        hybrid_path=hybrid_path,
        target_profile_name=target_label
    )

    results = report["report_data"]["benchmark_results"]
    winner = report["report_data"]["winner_mode"]

    print_header("BENCHMARK KIYASLAMA TABLOSU")
    print(f"{Fore.CYAN}{'Mod':<22} | {'Durum':<10} | {'Sıra':<8} | {'Test Edilen':<12} | {'Süre (sn)':<10} | {'Verimlilik':<10}{Style.RESET_ALL}")
    print("-" * 84)

    for r in results:
        status_color = Fore.GREEN if r["matched"] else Fore.RED
        pos_str = f"{r['position']:,}" if r["position"] else "-"
        eff_str = f"%{r['efficiency_score']}" if r["matched"] else "%0"
        print(
            f"{r['mode']:<22} | "
            f"{status_color}{r['status']:<10}{Style.RESET_ALL} | "
            f"{pos_str:<8} | "
            f"{r['tested_candidates']:<12,}"
            f" | {r['duration_seconds']:<10.4f} | "
            f"{Fore.YELLOW}{eff_str:<10}{Style.RESET_ALL}"
        )

    print("-" * 84)
    print_success(f"KAZANAN LİSTE: {Fore.YELLOW}{Style.BRIGHT}{winner}{Style.RESET_ALL}")
    print_info(f"Rapor Kaydedildi: {report['report_path']}")
    pause_prompt()


def exit_application() -> NoReturn:
    """Uygulamayı güvenli ve temiz bir şekilde sonlandırır."""
    print("\n")
    print_info("Cybzenor kapatılıyor. Güvenli çalışmalar dileriz.")
    logger.info("Uygulama kullanıcı talebiyle normal olarak kapatıldı.")
    sys.exit(0)


def main() -> None:
    """Ana CLI döngüsü ve komut yönlendiricisi."""
    setup_terminal_encoding()

    # Eğer komut satırı argümanları verildiyse doğrudan çalıştır (örn: python main.py view 10)
    if len(sys.argv) > 1:
        from cybzenor import run_cli_arguments
        run_cli_arguments()
        return

    logger.info(f"{settings.app_name} v{settings.version} başlatıldı.")

    while True:
        try:
            clear_screen()
            print_banner(version=settings.version)
            display_system_status()
            display_menu()

            active_target = get_active_target()
            prompt_label = f"cybzenor ({Fore.CYAN}{active_target}{Fore.GREEN}) > " if active_target else "cybzenor [1-7 veya komut]: "
            choice = input(f"{Fore.GREEN}{Style.BRIGHT}{prompt_label}{Style.RESET_ALL}").strip()

            if not choice:
                continue

            # Doğrudan komut kontrolü (örn: 'view 10', 'list', 'search krakoç')
            if execute_fast_command(choice):
                continue

            if choice == "1":
                handle_default_wordlist_operations()
            elif choice == "2":
                handle_targeted_wordlist_generation()
            elif choice == "3":
                handle_hybrid_wordlist_generation()
            elif choice == "4":
                handle_local_hash_audit_engine()
            elif choice == "5":
                handle_online_login_audit()
            elif choice == "6":
                handle_benchmark_module()
            elif choice == "7":
                exit_application()
            else:
                print_error("Geçersiz seçim! Lütfen 1 ile 7 arasında bir rakam girin veya bir komut yazın (örn: 'view 10', 'list').")
                pause_prompt()

        except KeyboardInterrupt:
            print("\n")
            print_warning("İşlem kullanıcı tarafından (Ctrl+C) iptal edildi.")
            exit_application()
        except Exception as e:
            logger.exception(f"Beklenmeyen bir hata oluştu: {e}")
            print_error(f"Beklenmeyen bir hata: {e}")
            pause_prompt()


if __name__ == "__main__":
    main()
