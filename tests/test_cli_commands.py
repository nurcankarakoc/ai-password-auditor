"""
Smart Password Auditor (SPA / Cybzenor) - CLI Komut Modülü Testleri
'list', 'view', 'tail', 'search' hızlı komutlarının birim testleri.
"""

import pytest
from pathlib import Path
from core.cli_commands import (
    resolve_wordlist_file,
    cmd_view_wordlist,
    cmd_search_wordlist,
    execute_fast_command
)
from core.wordlist_manager import wordlist_manager


class TestCLICommands:
    """Doğrudan komut yöneticisi testleri."""

    def test_resolve_wordlist_file_default(self):
        """'default' anahtar kelimesinin default.txt dosyasını çözdüğünü doğrula."""
        path = resolve_wordlist_file("default")
        assert path == wordlist_manager.default_wordlist_path

    def test_resolve_wordlist_file_latest(self):
        """Parametre verilmediğinde son üretilen veya varsayılan dosyanın döndüğünü doğrula."""
        path = resolve_wordlist_file()
        assert path is not None
        assert path.is_file()

    def test_execute_fast_command_view(self, capsys):
        """'view 5' komutunun başarıyla işlendiğini doğrula."""
        handled = execute_fast_command("view 5", pause=False)
        assert handled is True
        captured = capsys.readouterr()
        assert "PAROLA HAVUZU" in captured.out

    def test_execute_fast_command_list(self, capsys):
        """'list' komutunun hedef tablosunu yazdırdığını doğrula."""
        handled = execute_fast_command("list", pause=False)
        assert handled is True
        captured = capsys.readouterr()
        assert "HEDEF DOSYALARI" in captured.out

    def test_execute_fast_command_help(self, capsys):
        """'help' komutunun komut kılavuzunu yazdırdığını doğrula."""
        handled = execute_fast_command("help", pause=False)
        assert handled is True
        captured = capsys.readouterr()
        assert "CYBZENOR" in captured.out

    def test_execute_fast_command_ignores_menu_numbers(self):
        """1-7 arasındaki menü seçimlerinin fast command tarafından yutulmadığını doğrula."""
        for num in ["1", "2", "3", "4", "5", "6", "7"]:
            assert execute_fast_command(num, pause=False) is False
