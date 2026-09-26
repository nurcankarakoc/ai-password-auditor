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

from utils.platform_helper import setup_terminal_encoding

# Windows'ta konsolun varsayılan kod sayfası (örn. GitHub Actions runner'larında cp1252)
# Türkçe karakterler (ş, ğ, ı vb.) içeren print() çağrılarında UnicodeEncodeError ile
# ANINDA çökmeye neden oluyordu — bu betiğin kendi çıktısı için de aynı düzeltme uygulanır.
setup_terminal_encoding()

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

    # llama-cpp-python kurulu mu? Kurulu değilse .exe'ye gömülemez ama yine de derlenebilir;
    # kullanıcı Ayarlar sayfasından yerel AI modelini ayrıca indirip yükleyebilir.
    try:
        import llama_cpp  # noqa: F401
        _has_llama = True
    except ImportError:
        _has_llama = False
        print("[UYARI] llama-cpp-python kurulu değil — .exe, yerel AI gömülü olmadan derleniyor.")

    # Model dosyası (.gguf) diskte var mı? Varsa .exe'nin İÇİNE gömülür — böylece kullanıcı
    # .exe'yi açar açmaz, hiçbir ek indirme/tıklama yapmadan yapay zeka aktif olur (bkz.
    # config/settings.py::_ensure_seed_data_when_frozen). Yoksa (henüz 'python setup_local_ai.py'
    # çalıştırılmamışsa) .exe yine de derlenir, sadece AI ilk açılışta kurulu gelmez.
    from ai.local_llm_engine import MODELS_DIR, DEFAULT_FILENAME
    model_path = MODELS_DIR / DEFAULT_FILENAME
    if model_path.is_file():
        print(f"[*] Yerel AI modeli bulundu, .exe'ye gömülecek: {model_path.name} "
              f"({round(model_path.stat().st_size / (1024 * 1024)):,} MB)")
    else:
        print(
            f"[UYARI] {model_path} bulunamadı — .exe'ye yerel AI modeli GÖMÜLMEYECEK "
            f"(kullanıcı Ayarlar sayfasından sonradan indirebilir). Modeli önceden gömmek "
            f"için önce 'python setup_local_ai.py' çalıştırıp tekrar derleyin."
        )

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
        # huggingface_hub'ı --collect-all ile eklemiyoruz: onun opsiyonel CLI/inference
        # eklentileri (gradio/matplotlib benzeri ağır bağımlılıkları tetikleyebiliyor)
        # gereksiz yere .exe'yi şişiriyor (ve CI'da derlemeyi başarısız kılabiliyor).
        # local_llm_engine.py sadece hf_hub_download'ı kullanıyor; normal import taraması
        # bunu zaten yakalar, gerekirse aşağıdaki hidden-import güvenlik ağı yeter.
        "--hidden-import", "huggingface_hub",
    ]

    if _has_llama:
        args += ["--collect-all", "llama_cpp"]
    if model_path.is_file():
        args += ["--add-data", _add_data(model_path, "models")]

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
