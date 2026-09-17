"""
Cybzenor - Komut Satırı ve Siber Hedef Yöneticisi (Target Workspace)
Gerçek bir siber güvenlik aracı mantığıyla hedef profilleri (dossiers), aktif hedef (use target)
ve doğrudan komutları ('view 10', 'targets', 'use krakoç', 'info') yönetir.
"""

from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from colorama import Fore, Style
import re
import json

from config.settings import BASE_DIR
from core.wordlist_manager import wordlist_manager
from utils.platform_helper import print_header, print_info, print_success, print_warning, print_error, pause_prompt


# Oturum boyunca seçilen aktif hedef (Active Target Workspace)
ACTIVE_TARGET: Optional[str] = None


def get_active_target() -> Optional[str]:
    """Mevcut aktif hedefi döndürür."""
    global ACTIVE_TARGET
    return ACTIVE_TARGET


def set_active_target(target_name: Optional[str]) -> None:
    """Aktif hedefi günceller."""
    global ACTIVE_TARGET
    ACTIVE_TARGET = target_name


def parse_target_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wordlist öğesinden hedef kimliği ve profil özetini çıkarır.
    Metadata yoksa veya eksikse dosya adından zekice hedefin kimliğini çözer.
    """
    fname = item["name"]
    meta = item.get("metadata") or {}

    # 1. Hedef ID tespiti
    target_id = meta.get("target_id")
    if not target_id:
        m = re.search(r"(?:ai_targeted|hybrid)_([a-zA-Z0-9çğıöşüÇĞİÖŞÜ_]+?)_\d{8}_\d{6}", fname)
        if m:
            target_id = m.group(1)
        elif "default" in fname.lower():
            target_id = "default"
        else:
            target_id = fname.replace(".txt", "")

    # 2. Profil Detayları
    details = meta.get("target_profile_details") or {}
    names = details.get("names") or []
    dates = details.get("dates") or []
    interests = details.get("interests") or []
    locations = details.get("locations") or []
    keywords = details.get("keywords") or []

    # Eğer detay boşsa dosya adındaki hedefi isim olarak varsay
    if not names and target_id != "default":
        names = [target_id.capitalize()]

    # Okunaklı özet dizgesi
    summary_parts = []
    if names:
        summary_parts.append(f"İsimler: {', '.join(names)}")
    if dates:
        summary_parts.append(f"Yıllar: {', '.join(dates)}")
    if interests:
        summary_parts.append(f"İlgi: {', '.join(interests)}")
    if locations:
        summary_parts.append(f"Şehir: {', '.join(locations)}")
    if keywords:
        summary_parts.append(f"Ek: {', '.join(keywords)}")

    profile_summary_str = " | ".join(summary_parts) if summary_parts else "Genel / Profil Belirtilmemiş"

    return {
        "target_id": target_id,
        "profile_summary": profile_summary_str,
        "details": details,
        "password_policy": meta.get("password_policy", ""),
        "priority_distribution": meta.get("priority_distribution", {}),
        "type": meta.get("type", "AI_TARGETED" if "ai_targeted" in fname else "HYBRID" if "hybrid" in fname else "CUSTOM")
    }


def resolve_wordlist_file(target: Optional[str] = None) -> Optional[Path]:
    """
    Kullanıcının girdiği hedef parametresini (hedef adı, dosya adı, indeks numarası) çözer.
    Belirtilmemişse sırasıyla:
    1. Aktif seçili hedef (ACTIVE_TARGET)
    2. En son üretilen liste
    3. Varsayılan liste
    """
    global ACTIVE_TARGET
    generated_lists = wordlist_manager.list_generated_wordlists()

    # Eğer hedef girilmemişse aktif hedefi kullan
    effective_target = target
    if not effective_target or effective_target.strip() == "":
        if ACTIVE_TARGET:
            effective_target = ACTIVE_TARGET
        elif generated_lists:
            return generated_lists[0]["path"]
        elif wordlist_manager.default_wordlist_path.is_file():
            return wordlist_manager.default_wordlist_path
        else:
            return None

    cleaned = effective_target.strip().lower()

    # 'default' kelimesi girildiyse
    if cleaned in ["default", "default.txt", "varsayilan"]:
        return wordlist_manager.default_wordlist_path

    # İndeks numarası girildiyse (1, 2, 3...)
    if cleaned.isdigit():
        idx = int(cleaned) - 1
        if 0 <= idx < len(generated_lists):
            return generated_lists[idx]["path"]

    # Hedef kimliği (target_id) veya dosya adı eşleşmesi
    for item in generated_lists:
        parsed = parse_target_metadata(item)
        if cleaned == parsed["target_id"].lower() or cleaned in item["name"].lower():
            return item["path"]

    # Doğrudan dosya yolu girildiyse
    direct_path = Path(effective_target)
    if direct_path.is_file():
        return direct_path

    gen_path = wordlist_manager.generated_dir / effective_target
    if gen_path.is_file():
        return gen_path

    return None


def select_target_interactive(prompt_msg: str = "Hangi hedef listeyi incelemek istersiniz?") -> Optional[Path]:
    """
    Birden fazla hedef liste olduğunda kullanıcıya net, açıklayıcı bir hedef menüsü sunar.
    """
    items = wordlist_manager.list_generated_wordlists()
    if not items:
        if wordlist_manager.default_wordlist_path.is_file():
            return wordlist_manager.default_wordlist_path
        return None

    import sys
    if not sys.stdin.isatty():
        return items[0]["path"]

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}[ CYBZENOR HEDEF SEÇİCİ ]{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}Mevcut hedef profillerinden birini seçebilir veya Enter'a basarak son listeyi alabilirsiniz:{Style.RESET_ALL}\n")

    for idx, item in enumerate(items, 1):
        parsed = parse_target_metadata(item)
        tid = parsed["target_id"]
        cands = f"{item['total_candidates']:,}" if item.get('total_candidates') else "Bilinmiyor"
        prof = parsed["profile_summary"]
        is_active = " (AKTİF HEDEF)" if ACTIVE_TARGET and tid.lower() == ACTIVE_TARGET.lower() else ""

        print(f" {Fore.CYAN}[{idx}]{Style.RESET_ALL} {Fore.GREEN}{Style.BRIGHT}{tid:<12}{Style.RESET_ALL} | {cands:>6} Aday | {Fore.WHITE}{prof}{Style.RESET_ALL}{Fore.YELLOW}{is_active}{Style.RESET_ALL}")

    print(f" {Fore.CYAN}[{len(items) + 1}]{Style.RESET_ALL} default      | Varsayılan 2.500 Parolalık Genel Liste")

    sel = input(f"\n{Fore.GREEN}{prompt_msg} [1-{len(items) + 1}, Varsayılan: 1]: {Style.RESET_ALL}").strip()
    if not sel or sel == "1":
        return items[0]["path"]
    if sel == str(len(items) + 1) or sel.lower() in ["default", "varsayilan"]:
        return wordlist_manager.default_wordlist_path

    if sel.isdigit():
        idx = int(sel) - 1
        if 0 <= idx < len(items):
            return items[idx]["path"]

    # Metin olarak hedef adı girildiyse
    res = resolve_wordlist_file(sel)
    return res or items[0]["path"]


def cmd_list_targets() -> None:
    """Tüm hedef profillerini (Cyber Target Dossiers) ayrıntılı tablo ve kartlar halinde listeler."""
    print_header("HEDEF DOSYALARI VE PROFİLLER (Cybzenor Target Intelligence)")

    items = wordlist_manager.list_generated_wordlists()

    if not items:
        print_info("Sistemde kayıtlı hedef profili bulunamadı.")
        print_info("Yeni bir hedef oluşturmak için Menü [2] (AI Targeted) kullanabilirsiniz.")
        return

    print(f"{Fore.LIGHTBLACK_EX}Sistemde {len(items)} adet kayıtlı hedef profili bulunmaktadır:{Style.RESET_ALL}\n")

    for idx, item in enumerate(items, 1):
        parsed = parse_target_metadata(item)
        tid = parsed["target_id"]
        size_kb = f"{round(item['size_bytes'] / 1024, 1)} KB"
        cand_str = f"{item['total_candidates']:,}" if item.get('total_candidates') else "Bilinmiyor"
        is_active_badge = f"{Fore.YELLOW}{Style.BRIGHT} [AKTİF HEDEF]{Style.RESET_ALL}" if ACTIVE_TARGET and tid.lower() == ACTIVE_TARGET.lower() else ""

        print(f"{Fore.CYAN}+-- [{idx}] HEDEF: {Fore.GREEN}{Style.BRIGHT}{tid.upper()}{Style.RESET_ALL}{is_active_badge}")
        print(f"{Fore.CYAN}|{Style.RESET_ALL}   • Profil İstihbaratı : {Fore.WHITE}{parsed['profile_summary']}{Style.RESET_ALL}")
        if parsed.get("password_policy"):
            print(f"{Fore.CYAN}|{Style.RESET_ALL}   • Parola Politikası  : {Fore.YELLOW}{parsed['password_policy']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}|{Style.RESET_ALL}   • Parola Havuzu      : {Fore.YELLOW}{cand_str} aday{Style.RESET_ALL} ({size_kb}) | Tür: {parsed['type']}")
        
        # Öncelik dağılımı varsa göster
        pdist = parsed.get("priority_distribution", {})
        if pdist:
            print(f"{Fore.CYAN}|{Style.RESET_ALL}   • Öncelik Kademeleri : P1 (Yüksek): {pdist.get('priority_1_high', 0):,}, P2 (Orta): {pdist.get('priority_2_medium', 0):,}, P3 (Leetspeak): {pdist.get('priority_3_low', 0):,}")
        
        print(f"{Fore.CYAN}+--{Style.RESET_ALL}   • Dosya: {Fore.LIGHTBLACK_EX}{item['name']}{Style.RESET_ALL} (Oluşturulma: {item['mtime_str']})\n")

    print("-" * 75)
    print(f"{Fore.LIGHTBLACK_EX}Komutlar:{Style.RESET_ALL}")
    print(f" • Bir hedefi aktif yapmak için: {Fore.CYAN}use <hedef veya no>{Style.RESET_ALL}  (Örn: 'use krakoç' veya 'use 1')")
    print(f" • Parolaları incelemek için   : {Fore.CYAN}view <hedef veya no> [n]{Style.RESET_ALL} (Örn: 'view krakoç 10' veya 'view 10')")
    print(f" • Detaylı hedef kartı için    : {Fore.CYAN}info <hedef>{Style.RESET_ALL}          (Örn: 'info krakoç')")


cmd_list_wordlists = cmd_list_targets


def cmd_use_target(target: str) -> None:
    """Belirtilen hedefi aktif hedef (Workspace) olarak ayarlar."""
    target_path = resolve_wordlist_file(target)
    if not target_path or not target_path.is_file():
        print_error(f"Hedef bulunamadı: '{target}'")
        print_info("Mevcut hedefleri görmek için 'targets' veya 'list' yazabilirsiniz.")
        return

    # Hedef adını bul
    generated_lists = wordlist_manager.list_generated_wordlists()
    found_id = target
    for item in generated_lists:
        if item["path"] == target_path:
            found_id = parse_target_metadata(item)["target_id"]
            break

    set_active_target(found_id)
    print_success(f"AKTİF HEDEF SEÇİLDİ: {Fore.YELLOW}{Style.BRIGHT}{found_id.upper()}{Style.RESET_ALL}")
    print_info(f"Bağlı Liste: {target_path.name}")
    print(f"{Fore.LIGHTBLACK_EX}Artık 'view 10', 'search', 'audit' komutları doğrudan bu hedef üzerinde çalışacaktır.{Style.RESET_ALL}")


def cmd_view_wordlist(target: Optional[str] = None, n: int = 10, tail: bool = False) -> None:
    """
    Seçilen veya aktif hedef wordlist'in ilk N (veya son N) satırını satır numaralarıyla görüntüler.
    Eğer birden fazla liste varsa ve hedef belirtilmemişse akıllı seçici devreye girer.
    """
    # Eğer hedef açıkça girilmemişse ve aktif hedef yoksa ama birden fazla liste varsa seçtir
    target_path = None
    if not target:
        if ACTIVE_TARGET:
            target_path = resolve_wordlist_file(ACTIVE_TARGET)
        else:
            generated_lists = wordlist_manager.list_generated_wordlists()
            if len(generated_lists) > 1:
                target_path = select_target_interactive("Hangi hedefin parolasını görüntülemek istersiniz?")
            elif generated_lists:
                target_path = generated_lists[0]["path"]
            else:
                target_path = wordlist_manager.default_wordlist_path
    else:
        target_path = resolve_wordlist_file(target)

    if not target_path or not target_path.is_file():
        print_error(f"Görüntülenecek wordlist dosyası bulunamadı: '{target or 'En son üretilen'}'")
        print_info("Mevcut hedefleri görmek için 'targets' yazabilirsiniz.")
        return

    stats = wordlist_manager.get_wordlist_stats(target_path)
    total_lines = stats["total_lines"]

    lines = wordlist_manager.get_tail(target_path, n) if tail else wordlist_manager.get_head(target_path, n)

    header_mode = f"SON {len(lines)}" if tail else f"İLK {len(lines)}"
    
    # Hedef adını bul
    t_name = target_path.name
    generated_lists = wordlist_manager.list_generated_wordlists()
    for item in generated_lists:
        if item["path"] == target_path:
            t_name = f"{parse_target_metadata(item)['target_id'].upper()} ({target_path.name})"
            break

    print_header(f"HEDEF PAROLA HAVUZU: {t_name} ({header_mode} ADAY)")
    print(f" • Toplam Aday : {Fore.YELLOW}{total_lines:,}{Style.RESET_ALL} parola")
    print(f" • Dosya Boyutu: {round(stats['file_size_bytes'] / 1024, 2)} KB")
    
    if "metadata" in stats:
        meta = stats["metadata"]
        if meta.get("password_policy"):
            print(f" • Politika    : {Fore.YELLOW}{meta['password_policy']}{Style.RESET_ALL}")
        if "target_profile_details" in meta:
            det = meta["target_profile_details"]
            summary = f"İsimler: {det.get('names')}, Yıllar: {det.get('dates')}, İlgi: {det.get('interests')}"
            print(f" • Hedef Bilgi : {Fore.CYAN}{summary}{Style.RESET_ALL}")
    print("-" * 65)

    for line_num, pwd in lines:
        print(f" {Fore.CYAN}[{line_num:>5}]{Style.RESET_ALL} {Fore.WHITE}{Style.BRIGHT}{pwd}{Style.RESET_ALL}")

    print("-" * 65)
    print(f"{Fore.LIGHTBLACK_EX}Gösterilen: {len(lines)} satır / Toplam: {total_lines:,} satır.{Style.RESET_ALL}")


def cmd_search_wordlist(query: str, target: Optional[str] = None, max_results: int = 30) -> None:
    """Wordlist içinde arama yapar ve eşleşen satırları satır numaralarıyla gösterir."""
    target_path = resolve_wordlist_file(target)
    if not target_path or not target_path.is_file():
        print_error(f"Aranacak wordlist bulunamadı: '{target or 'En son üretilen'}'")
        return

    print_header(f"WORDLIST ARAMA: '{query}' -> {target_path.name}")
    matches = wordlist_manager.search_lines(target_path, query, max_results=max_results)

    if not matches:
        print_warning(f"'{query}' ifadesini içeren bir parola bulunamadı.")
        return

    print_success(f"{len(matches)} eşleşme bulundu (Maksimum {max_results} gösteriliyor):")
    print("-" * 65)
    for line_num, pwd in matches:
        highlighted = re.sub(f"({re.escape(query)})", f"{Fore.YELLOW}{Style.BRIGHT}\\1{Fore.WHITE}", pwd, flags=re.IGNORECASE)
        print(f" {Fore.CYAN}[{line_num:>5}]{Style.RESET_ALL} {Fore.WHITE}{highlighted}{Style.RESET_ALL}")
    print("-" * 65)


def cmd_target_info(target: Optional[str] = None) -> None:
    """Hedefin tüm siber istihbarat künyesini (Dossier) görüntüler."""
    target_path = resolve_wordlist_file(target)
    if not target_path or not target_path.is_file():
        print_error(f"Hedef bulunamadı: '{target or 'Aktif hedef'}'")
        return

    stats = wordlist_manager.get_wordlist_stats(target_path)
    meta = stats.get("metadata", {})

    print_header(f"HEDEF SİBER İSTİHBARAT KÜNYESİ: {target_path.name}")
    print(f" • Hedef Tanımı     : {Fore.GREEN}{Style.BRIGHT}{meta.get('target_id', 'Bilinmiyor').upper()}{Style.RESET_ALL}")
    print(f" • Liste Türü       : {meta.get('type', 'CUSTOM')}")
    print(f" • Toplam Parola    : {Fore.YELLOW}{stats['total_lines']:,}{Style.RESET_ALL} adet")
    print(f" • Dosya Boyutu     : {round(stats['file_size_bytes'] / 1024, 2)} KB")
    print(f" • Üretilme Tarihi  : {meta.get('created_at', 'Bilinmiyor')}")

    details = meta.get("target_profile_details", {})
    if details:
        print(f"\n{Fore.YELLOW}[ TOPLANAN OSINT VERİLERİ ]{Style.RESET_ALL}")
        print(f" • İsimler / Aile   : {', '.join(details.get('names', [])) or '-'}")
        print(f" • Önemli Tarihler  : {', '.join(details.get('dates', [])) or '-'}")
        print(f" • Konum / Plaka    : {', '.join(details.get('locations', [])) or '-'}")
        print(f" • İlgi / Takım     : {', '.join(details.get('interests', [])) or '-'}")
        print(f" • Anahtar Kelimeler: {', '.join(details.get('keywords', [])) or '-'}")

    pdist = meta.get("priority_distribution", {})
    if pdist:
        print(f"\n{Fore.YELLOW}[ SKORLAMA VE ÖNCELİK DAĞILIMI ]{Style.RESET_ALL}")
        print(f" • Priority 1 (En Yüksek / İsim+Yıl): {pdist.get('priority_1_high', 0):,} parola")
        print(f" • Priority 2 (Orta / Ekler+Hobiler): {pdist.get('priority_2_medium', 0):,} parola")
        print(f" • Priority 3 (Düşük / Leetspeak)   : {pdist.get('priority_3_low', 0):,} parola")


def print_command_help() -> None:
    """Kullanılabilir doğrudan siber komutları listeler."""
    print_header("CYBZENOR / SİBER KOMUT SATIRI KILAVUZU")
    print("Menü numarası [1-7] girmek yerine aşağıdaki profesyonel komutları yazabilirsiniz:\n")
    print(f" {Fore.CYAN}targets / list / ls{Style.RESET_ALL}     : Tüm hedefleri (Dossiers), profil bilgileri ve sayılarıyla listeler.")
    print(f" {Fore.CYAN}use <hedef veya no>{Style.RESET_ALL}     : Bir hedefi AKTİF yapar (Örn: 'use target_01' veya 'use 1').")
    print(f" {Fore.CYAN}view [n]{Style.RESET_ALL}                : Aktif/seçili hedefin ilk n (örn: 10) parolasını görüntüler.")
    print(f" {Fore.CYAN}view <hedef> [n]{Style.RESET_ALL}        : İstenen hedefin ilk n parolasını görüntüler (Örn: 'view target_01 15').")
    print(f" {Fore.CYAN}tail [n]{Style.RESET_ALL}                : Hedefin son n parolasını görüntüler.")
    print(f" {Fore.CYAN}info <hedef>{Style.RESET_ALL}            : Hedefin toplanan tüm OSINT profil detaylarını gösterir.")
    print(f" {Fore.CYAN}search <kelime>{Style.RESET_ALL}         : Wordlist içinde arama yapar (Örn: 'search pamuk').")
    print(f" {Fore.CYAN}unuse / back{Style.RESET_ALL}            : Aktif hedef seçimini temizler.")
    print(f" {Fore.CYAN}apikey{Style.RESET_ALL}                  : Gemini API anahtarınızı ekler/günceller (AI özelliklerini güçlendirir).")
    print(f" {Fore.CYAN}help / ?{Style.RESET_ALL}                : Bu yardım ekranını gösterir.")
    print(f" {Fore.CYAN}exit / q{Style.RESET_ALL}                : Programdan çıkar.\n")
    print(f"{Fore.LIGHTBLACK_EX}Örnek: 'targets' yazıp hedefleri görebilir, 'use target_01' ile aktif edip 'view 10' diyebilirsiniz.{Style.RESET_ALL}")


def execute_fast_command(cmd_text: str, pause: bool = True) -> bool:
    """
    Kullanıcının girdiği metni komut olarak değerlendirir.
    Geçerli bir komut ise çalıştırıp True döner.
    Standart menü seçimi (1-7) veya boşluk ise False döner.
    """
    raw = cmd_text.strip()
    if not raw:
        return False

    if raw in ["1", "2", "3", "4", "5", "6", "7"]:
        return False

    tokens = raw.split()
    cmd = tokens[0].lower()
    args = tokens[1:]

    def maybe_pause():
        if pause:
            pause_prompt()

    # 1. Yardım
    if cmd in ["help", "komut", "komutlar", "?", "man"]:
        print_command_help()
        maybe_pause()
        return True

    # 2. Hedef listesi (targets / list / ls)
    if cmd in ["targets", "target", "hedefler", "list", "ls", "dir", "profiles"]:
        cmd_list_targets()
        maybe_pause()
        return True

    # 3. Aktif hedef seçimi (use <target>)
    if cmd in ["use", "sec", "seç", "select"]:
        if len(args) == 0:
            chosen = select_target_interactive("Aktif yapmak istediğiniz hedefi seçin:")
            if chosen:
                cmd_use_target(chosen.name)
        else:
            cmd_use_target(args[0])
        maybe_pause()
        return True

    # 4. Aktif hedefi bırak (unuse / back)
    if cmd in ["unuse", "back", "geri"]:
        set_active_target(None)
        print_info("Aktif hedef seçimi temizlendi.")
        maybe_pause()
        return True

    # 5. Hedef detay künyesi (info / dossier)
    if cmd in ["info", "bilgi", "dossier", "profil"]:
        target = args[0] if args else None
        cmd_target_info(target=target)
        maybe_pause()
        return True

    # 6. Görüntüleme (view / show / head / cat)
    if cmd in ["view", "show", "head", "cat", "goruntule"]:
        target = None
        count = 10

        if len(args) == 0:
            target = None
            count = 10
        elif len(args) == 1:
            if args[0].isdigit():
                count = int(args[0])
                target = None
            else:
                target = args[0]
                count = 10
        elif len(args) >= 2:
            if args[1].isdigit():
                target = args[0]
                count = int(args[1])
            elif args[0].isdigit():
                count = int(args[0])
                target = args[1]
            else:
                target = args[0]

        cmd_view_wordlist(target=target, n=count, tail=False)
        maybe_pause()
        return True

    # 7. Son satırlar (tail)
    if cmd in ["tail", "son"]:
        target = None
        count = 10
        if len(args) == 1 and args[0].isdigit():
            count = int(args[0])
        elif len(args) >= 2 and args[1].isdigit():
            target = args[0]
            count = int(args[1])
        cmd_view_wordlist(target=target, n=count, tail=True)
        maybe_pause()
        return True

    # 8. Arama (search / find / ara)
    if cmd in ["search", "find", "ara", "grep"]:
        if len(args) == 0:
            print_error("Lütfen aranacak kelimeyi belirtin. Örn: 'search pamuk'")
            maybe_pause()
            return True
        query = args[0]
        target = args[1] if len(args) > 1 else None
        cmd_search_wordlist(query=query, target=target)
        maybe_pause()
        return True

    # 9b. Gemini API anahtarı ekleme/güncelleme (apikey)
    if cmd in ["apikey", "api-key", "anahtar"]:
        from config.settings import settings, save_gemini_api_key
        print_header("GEMINI API ANAHTARI")
        if settings.gemini_api_key:
            masked = settings.gemini_api_key[:6] + "..." + settings.gemini_api_key[-4:]
            print(f"{Fore.LIGHTBLACK_EX}Mevcut anahtar: {masked}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}Ücretsiz anahtar almak için: https://aistudio.google.com/apikey{Style.RESET_ALL}")
        new_key = input(f"{Fore.GREEN}Yeni Gemini API anahtarınızı yapıştırın [ENTER = vazgeç]: {Style.RESET_ALL}").strip()
        if new_key:
            save_gemini_api_key(new_key)
            print_success("API anahtarı kaydedildi. Artık AI özellikleri Gemini üzerinden çalışacak.")
        else:
            print_info("İşlem iptal edildi.")
        maybe_pause()
        return True

    # 9. Çıkış
    if cmd in ["exit", "quit", "q", "cikis", "çıkış"]:
        import sys
        print(f"\n{Fore.CYAN}Cybzenor kapatılıyor. Güvenli çalışmalar dileriz.{Style.RESET_ALL}")
        sys.exit(0)

    # Tanınmayan komut
    print_warning(f"Tanınmayan komut veya seçim: '{cmd}'")
    print_info("Mevcut hedefleri görmek için 'targets', komut yardımı için 'help' yazabilirsiniz.")
    maybe_pause()
    return True
