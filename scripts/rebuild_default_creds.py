#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cybzenor - wordlists/default.txt "Varsayilan Kimlik Bilgisi" Kokleri Yeniden Insasi
(tek seferlik betik)

Sorun: dosya zaman icinde parca parca buyutuldugu icin en degerli/en cok gercek
hayatta karsilasilan kokler (admin, root, password, guest, test...) TUTARSIZ ve
EKSIK ek/ozel-karakter kapsamiyla, ayni koke ait birbirinden kopuk mini-bloklar
halinde dagilmisti (orn. "admin123!" var ama "admin123?", "admin123@",
"admin123#" yoktu; UPPER-case varyantlari sadece bazi kokler icin vardi).
Kullanici bunu haklı olarak "kaliteli bir brute-force araci degil" diye
elestirdi (bkz. "admin123?" ornegi).

Bu betik: bu koklere ait TUM eski, dagilmis satirlari dosyadan siler, sonra
HER kok icin AYNI, kapsamli ve tutarli bir ek/varyant setiyle TEK bir blok
yeniden uretir. Marka/urun adlari (turktelekom, mikrotik, wordpress vb.) BILINCLI
olarak bu kapsamin DISINDA tutulur -- onlar zaten kendi ic tutarli mini-
bloklarinda kaliyor, degistirilmiyor.

Kullanim (tek seferlik, tekrar calistirmak idempotent DEGILDIR):
    python scripts/rebuild_default_creds.py
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TARGET = BASE_DIR / "wordlists" / "default.txt"

# Kapsamli yeniden uretimin uygulanacagi, gercek hayatta EN COK karsilasilan
# varsayilan/zayif kimlik bilgisi kokleri (marka/urun adlari HARIC).
CORE_ROOTS = [
    "admin", "root", "toor", "user", "guest", "password", "pass",
    "welcome", "administrator", "test", "demo", "deneme", "master",
    "default", "manager", "operator", "system", "superadmin", "support", "service",
]

# Sayisal/ek varyantlari: en yaygin insan ve router/IoT varsayilan kaliplari.
NUMERIC_SUFFIXES = ["1", "12", "123", "1234", "12345", "123456", "01", "07"]
YEAR_SUFFIXES = ["2023", "2024", "2025"]
SPECIAL_CHARS = ["!", "@", "#", "$", ".", "_", "?", "*"]
# "123" + ozel karakter kombinasyonu (en yaygin "sayi sonra ozel karakter" kalibi)
NUM_SPECIAL_COMBOS = [f"123{sp}" for sp in SPECIAL_CHARS]


def _variants_for_root(root: str) -> list[str]:
    """Bir kok icin lower/Capitalized/UPPER x tum ek kombinasyonlarini uretir."""
    casings = [root.lower(), root.capitalize(), root.upper()]
    # UPPER, lower'a esitse (orn. tek harfli veya zaten tamami buyuk bir kok
    # yoksa) mukerrer eklenmesin diye sirali-tekil (dict.fromkeys) kullanilir.
    casings = list(dict.fromkeys(casings))

    suffixes = [""] + NUMERIC_SUFFIXES + YEAR_SUFFIXES + SPECIAL_CHARS + NUM_SPECIAL_COMBOS
    out = []
    for c in casings:
        for s in suffixes:
            out.append(f"{c}{s}")
    return list(dict.fromkeys(out))


def main() -> None:
    lines = TARGET.read_text(encoding="utf-8").splitlines()

    core_roots_lower = set(CORE_ROOTS)

    def is_stale_core_line(line: str) -> bool:
        """Satirin, CORE_ROOTS'tan birinin eski/dagilmis bir varyanti olup olmadigini
        (bastaki harf dizisini alip, kalanin sadece rakam/ozel karakter oldugunu
        kontrol ederek) belirler."""
        i = 0
        while i < len(line) and line[i].isalpha():
            i += 1
        root_part = line[:i].lower()
        rest = line[i:]
        if root_part not in core_roots_lower:
            return False
        # Kalan kismin TAMAMEN rakam/ozel karakterlerden olustugunu dogrula
        # (orn. "administrator123456" gibi baska bir kokle karismasin diye
        # root_part TAM ESLESME olmali, alt dize degil -- yukaridaki `i` zaten
        # ilk alfabetik olmayan karaktere kadar aldigi icin bu otomatik saglanir).
        return all((not ch.isalpha()) for ch in rest)

    kept = [l for l in lines if not is_stale_core_line(l)]
    removed_count = len(lines) - len(kept)

    new_block: list[str] = []
    seen_new = set()
    for root in CORE_ROOTS:
        for v in _variants_for_root(root):
            key = v.lower()
            if key not in seen_new:
                seen_new.add(key)
                new_block.append(v)

    # Yeni, kapsamli blok dosyanin EN BASINA eklenir (bu kokler en yuksek
    # olasilikli varsayilan kimlik bilgileridir, once denenmeli).
    output = new_block + kept

    TARGET.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"[+] {removed_count} eski/dagilmis satir silindi.")
    print(f"[+] {len(new_block)} yeni, tutarli/kapsamli satir eklendi ({len(CORE_ROOTS)} kok x ~{len(new_block)//len(CORE_ROOTS)} varyant).")
    print(f"[+] Toplam satir sayisi: {len(output)}")


if __name__ == "__main__":
    main()
