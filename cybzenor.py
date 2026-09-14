#!/usr/bin/env python3
"""
Cybzenor (Smart Password Auditor) - CLI ve Komut Satırı Arayüzü
Kullanıcıların 'python cybzenor.py view 10' veya doğrudan interaktif kabuk üzerinden
hızlıca wordlist'leri görüntülemesini, aramasını ve denetlemesini sağlar.
"""

import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.platform_helper import setup_terminal_encoding
from core.cli_commands import (
    cmd_list_wordlists,
    cmd_view_wordlist,
    cmd_search_wordlist,
    print_command_help,
    execute_fast_command
)
import main


def run_cli_arguments() -> None:
    """Komut satırı argümanları girilmişse doğrudan çalıştırır."""
    setup_terminal_encoding()
    args = sys.argv[1:]

    if not args:
        # Argüman yoksa ana interaktif menüyü başlat
        main.main()
        return

    cmd = args[0].lower()

    if cmd in ["-h", "--help", "help"]:
        print_command_help()
        return

    if cmd in ["list", "ls", "targets", "target", "profiles"]:
        cmd_list_wordlists()
        return

    if cmd in ["info", "bilgi", "dossier"]:
        from core.cli_commands import cmd_target_info
        target = args[1] if len(args) > 1 else None
        cmd_target_info(target=target)
        return

    if cmd in ["view", "show", "head", "cat"]:
        target = None
        count = 10
        rem = args[1:]
        if len(rem) == 1:
            if rem[0].isdigit():
                count = int(rem[0])
            else:
                target = rem[0]
        elif len(rem) >= 2:
            if rem[1].isdigit():
                target = rem[0]
                count = int(rem[1])
            elif rem[0].isdigit():
                count = int(rem[0])
                target = rem[1]
        cmd_view_wordlist(target=target, n=count, tail=False)
        return

    if cmd in ["tail"]:
        target = None
        count = 10
        rem = args[1:]
        if len(rem) == 1 and rem[0].isdigit():
            count = int(rem[0])
        elif len(rem) >= 2 and rem[1].isdigit():
            target = rem[0]
            count = int(rem[1])
        cmd_view_wordlist(target=target, n=count, tail=True)
        return

    if cmd in ["search", "find", "grep"]:
        if len(args) < 2:
            print("Kullanım: python cybzenor.py search <kelime> [hedef]")
            return
        query = args[1]
        target = args[2] if len(args) > 2 else None
        cmd_search_wordlist(query=query, target=target)
        return

    # Diğer tüm durumlar
    full_cmd = " ".join(args)
    if not execute_fast_command(full_cmd):
        print(f"Bilinmeyen komut: '{cmd}'. Yardım için 'python cybzenor.py help' yazınız.")


if __name__ == "__main__":
    run_cli_arguments()
