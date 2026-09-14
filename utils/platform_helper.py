"""
Smart Password Auditor (SPA) - Platform ve Terminal Yardımcısı
Windows ve Linux/macOS sistemlerde uyumlu ekran kontrolü, renklendirme ve UTF-8 yapılandırması.
"""

import os
import sys
import platform
from colorama import init, Fore, Style

# Colorama'yı başlat (autoreset=True ile stiller otomatik sıfırlanır)
init(autoreset=True)


def setup_terminal_encoding() -> None:
    """
    Windows komut satırında UTF-8 karakterlerin (Türkçe karakterler vb.)
    düzgün gösterilmesini sağlar.
    """
    if platform.system() == "Windows":
        try:
            # Python 3.7+ için konsol kodlamasını UTF-8'e zorla
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def clear_screen() -> None:
    """İşletim sistemine uygun ekran temizleme komutunu çalıştırır."""
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def print_banner(version: str = "1.0.0") -> None:
    """Uygulama açılışında gösterilen şık ve profesyonel CLI başlığı."""
    banner = (
        f"{Fore.CYAN}{Style.BRIGHT}\n"
        r"================================================================================" + "\n"
        r"   ____                      _     ____                                    _    " + "\n"
        r"  / ___| _ __ ___   __ _ _ _| |_  |  _ \ __ _ ___ _____      _____  _ __ __| |   " + "\n"
        r"  \___ \| '_ ` _ \ / _` | '__| __| | |_) / _` / __/ __\ \ /\ / / _ \| '__/ _` |   " + "\n"
        r"   ___) | | | | | | (_| | |  | |_  |  __/ (_| \__ \__ \\ V  V / (_) | | | (_| |   " + "\n"
        r"  |____/|_| |_| |_|\__,_|_|   \__| |_|   \__,_|___/___/ \_/\_/ \___/|_|  \__,_|   " + "\n"
        r"                                  AUDITOR                                       " + "\n"
        r"================================================================================" + f"{Style.RESET_ALL}\n"
        f"  {Fore.YELLOW}🛡️  Akıllı Hedefli Parola Denetim ve Güvenlik Araştırma Framework'ü{Style.RESET_ALL}\n"
        f"  {Fore.GREEN}● Sürüm:{Style.RESET_ALL} v{version}  |  {Fore.GREEN}● Mod:{Style.RESET_ALL} Yerel Denetim (Safety-First)  |  {Fore.GREEN}● OS:{Style.RESET_ALL} {platform.system()}\n"
        "================================================================================\n"
    )
    print(banner)


def print_success(message: str) -> None:
    """Başarı mesajı yazdırır (Yeşil)."""
    print(f"{Fore.GREEN}[+] {message}{Style.RESET_ALL}")


def print_info(message: str) -> None:
    """Bilgilendirme mesajı yazdırır (Mavi/Cyan)."""
    print(f"{Fore.CYAN}[*] {message}{Style.RESET_ALL}")


def print_warning(message: str) -> None:
    """Uyarı mesajı yazdırır (Sarı)."""
    print(f"{Fore.YELLOW}[!] {message}{Style.RESET_ALL}")


def print_error(message: str) -> None:
    """Hata mesajı yazdırır (Kırmızı)."""
    print(f"{Fore.RED}[-] {message}{Style.RESET_ALL}")


def print_header(title: str) -> None:
    """Bölüm başlığı yazdırır."""
    line = "-" * (len(title) + 4)
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{line}")
    print(f"  {title}")
    print(f"{line}{Style.RESET_ALL}")


def pause_prompt() -> None:
    """Kullanıcının devam etmek için Enter'a basmasını bekler."""
    print(f"\n{Fore.LIGHTBLACK_EX}Devam etmek için Enter tuşuna basınız...{Style.RESET_ALL}", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
