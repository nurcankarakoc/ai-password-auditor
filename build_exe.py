#!/usr/bin/env python3
"""
Cybzenor - Windows .exe Derleme Betiği
Masaüstü uygulamasını (launch_gui.py) PyInstaller ile tek bir çalıştırılabilir .exe
dosyasına paketler. Üretilen .exe hiçbir Python kurulumu gerektirmeden çalışır;
kullanıcı verisi (üretilen wordlist, hedef profilleri, loglar vb.) her zaman .exe'nin
yanındaki klasörde kalır (bkz. config/settings.py::_detect_base_dir).

Kullanım:
    pip install -r requirements.txt -r requirements-build.txt
    python build_exe.py

Çıktı: dist/Cybzenor.exe
"""

import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

BASE_DIR = Path(__file__).resolve().parent
DIST_NAME = "Cybzenor"


def _add_data(src: Path, dest_subdir: str) -> str:
    """PyInstaller --add-data argümanını platforma uygun ayraçla (Windows: ';', diğer: ':') üretir."""
    return f"{src}{os.pathsep}{dest_subdir}"


def main() -> None:
    default_wordlist = BASE_DIR / "wordlists" / "default.txt"
    default_config = BASE_DIR / "config" / "config.json"

    if not default_wordlist.is_file():
        print(f"[HATA] Beklenen dosya bulunamadı: {default_wordlist}")
        sys.exit(1)

    # Önceki derlemelerden kalan build/ ve dist/ klasörlerini temizle (--clean sadece
    # PyInstaller'ın kendi önbelleğini temizler, dist/'i temizlemez).
    for stale in ("build", "dist"):
        stale_path = BASE_DIR / stale
        if stale_path.is_dir():
            shutil.rmtree(stale_path, ignore_errors=True)

    args = [
        str(BASE_DIR / "launch_gui.py"),
        "--name", DIST_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths", str(BASE_DIR),
        "--add-data", _add_data(default_wordlist, "wordlists"),
        "--add-data", _add_data(default_config, "config"),
        "--collect-all", "customtkinter",
        "--collect-all", "darkdetect",
        "--collect-all", "llama_cpp",
        "--collect-all", "huggingface_hub",
    ]

    print("[*] PyInstaller derlemesi başlıyor (birkaç dakika sürebilir)...")
    PyInstaller.__main__.run(args)

    exe_path = BASE_DIR / "dist" / f"{DIST_NAME}.exe"
    if exe_path.is_file():
        size_mb = round(exe_path.stat().st_size / (1024 * 1024), 1)
        print(f"\n[+] Derleme tamamlandı: {exe_path} ({size_mb} MB)")
    else:
        print("\n[HATA] .exe dosyası oluşturulamadı, yukarıdaki PyInstaller çıktısını inceleyin.")
        sys.exit(1)


if __name__ == "__main__":
    main()
