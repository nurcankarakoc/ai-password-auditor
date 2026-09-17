#!/usr/bin/env python3
"""
Cybzenor - Yerel AI Motoru Kurulum Betiği (İsteğe Bağlı)
Gemini API anahtarı olmadan da gerçek bir yapay zeka kullanmak isteyenler için:
küçük bir yerel dil modelini (GGUF, ~1GB) indirir. Bu betik çalıştırılmazsa
Cybzenor normal şekilde çalışmaya devam eder (statik kural motoruna düşer).

Kullanım:
    python setup_local_ai.py
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def install_llama_cpp() -> bool:
    print("[*] llama-cpp-python kuruluyor (önceden derlenmiş wheel deneniyor)...")
    # Önce standart PyPI dene (Linux/macOS'ta genelde kaynaktan derler, gcc varsa sorun olmaz).
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "llama-cpp-python"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True

    print("[!] Standart kurulum başarısız oldu, önceden derlenmiş CPU wheel indeksi deneniyor...")
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--quiet", "llama-cpp-python",
            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"
        ],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True

    print("[HATA] llama-cpp-python kurulamadı.")
    print(result.stderr[-2000:])
    print("\nWindows'ta bu genelde bir C++ derleyicisi (Visual Studio Build Tools) eksikliğinden olur.")
    print("Linux'ta 'sudo apt install -y build-essential' ile gerekli araçları kurup tekrar deneyebilirsiniz.")
    return False


def download_model() -> bool:
    try:
        from huggingface_hub import hf_hub_download  # noqa: F401
    except ImportError:
        print("[*] huggingface_hub kuruluyor...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "huggingface_hub"], check=True)

    from ai.local_llm_engine import download_model as _download_model
    try:
        path = _download_model()
        print(f"[+] Model hazır: {path}")
        return True
    except Exception as e:
        print(f"[HATA] Model indirilemedi: {e}")
        return False


def main() -> None:
    print("=" * 70)
    print("  Cybzenor - Yerel AI Motoru Kurulumu")
    print("=" * 70)
    print("Bu betik ~1GB'lık bir dil modeli indirecek ve llama-cpp-python kütüphanesini")
    print("kuracaktır. İşlem birkaç dakika sürebilir.\n")

    if not install_llama_cpp():
        sys.exit(1)

    if not download_model():
        sys.exit(1)

    print("\n[+] Kurulum tamamlandı! Artık Gemini API anahtarı olmadan da Cybzenor")
    print("    yerel yapay zeka motorunu otomatik olarak kullanacaktır.")


if __name__ == "__main__":
    main()
