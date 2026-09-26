#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cybzenor - wordlists/default.txt Türkçe Karakter Düzeltme Betiği (tek seferlik)

Sorun: default.txt genişletilirken duygusal/kişisel/vatanseverlik temalı Türkçe
kelime kökleri yanlışlıkla ASCII'ye katlanmış yazılmıştı (örn. "vatanım" yerine
"vatanim", "şirket" yerine "sirket"). Türk kullanıcılar gerçek hayatta parola
üretirken çoğunlukla doğru Türkçe karakteri kullanır (klavye/işletim sistemi
Türkçe ise) — bu yüzden doğru yazım (örn. "vatanım") önceliklendirilmeli, ama
bazı kullanıcılar Türkçe karakter giremeyen sistemlerde ASCII halini de
("vatanim") kullanabildiği için o varyant da listede kalmalı, sadece daha
düşük öncelikte (dosyada doğru yazımdan SONRA).

Bu betik, bilinen ASCII->Türkçe kök eşlemesini kullanarak: ASCII kökten
üretilmiş HER satırın hemen ÖNÜNE, aynı ek (sayı/özel karakter) ve aynı
büyük/küçük harf düzenini koruyan doğru Türkçe karakterli halini ekler.
Teknik/marka kökleri (turktelekom, mikrotik, wordpress, sqlserver vb.) bilinçli
olarak dokunulmadan bırakılır — bunlar gerçek dünyada zaten ASCII kullanılan
ürün/marka adlarıdır, "düzeltilecek" bir Türkçe kelime değildir.

Kullanım (tek seferlik, tekrar çalıştırmak idempotent DEĞİLDİR):
    python scripts/fix_turkish_chars.py
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TARGET = BASE_DIR / "wordlists" / "default.txt"

# ASCII'ye katlanmış kök (küçük harf) -> doğru Türkçe kök (küçük harf).
# Sadece gerçekten bir Türkçe harf (ç, ğ, ı, ö, ş, ü) içermesi gereken kökler
# burada listelenir; zaten doğru olan veya teknik/marka kökler dahil edilmez.
CORRECTIONS = {
    "hosgeldiniz": "hoşgeldiniz",
    "sirket": "şirket",
    "degistir": "değiştir",
    "gecici": "geçici",
    "sifre": "şifre",
    "turkiye": "türkiye",
    "ataturk": "atatürk",
    "canim": "canım",
    "askim": "aşkım",
    "hayatim": "hayatım",
    "melegim": "meleğim",
    "caniminici": "canımıniçi",
    "gulum": "gülüm",
    "yildiz": "yıldız",
    "gunes": "güneş",
    "ozgurluk": "özgürlük",
    "huseyin": "hüseyin",
    "omer": "ömer",
    "ayse": "ayşe",
    "fenerbahce": "fenerbahçe",
    "besiktas": "beşiktaş",
    "turkiyem": "türkiyem",
    "vatanim": "vatanım",
    "bayragim": "bayrağım",
    "ayyildiz": "ayyıldız",
    "onuncuyil": "onuncuyıl",
    "sehit": "şehit",
    "sehitler": "şehitler",
    "anitkabir": "anıtkabir",
    "insallah": "inşallah",
    "masallah": "maşallah",
    "elhamdulillah": "elhamdülillah",
    "subhanallah": "sübhanallah",
    "kardes": "kardeş",
    "kardesim": "kardeşim",
    "guzelim": "güzelim",
    "tatlim": "tatlım",
    "omrum": "ömrüm",
    "kralicem": "kraliçem",
    "sekerim": "şekerim",
    "subat": "şubat",
    "mayis": "mayıs",
    "agustos": "ağustos",
    "eylul": "eylül",
    "kasim": "kasım",
    "aralik": "aralık",
    "diyarbakir": "diyarbakır",
    "mugla": "muğla",
    "pinar": "pınar",
    "kubra": "kübra",
    "busra": "büşra",
    "ozge": "özge",
    "yagmur": "yağmur",
    "nazli": "nazlı",
    "asli": "aslı",
    "baris": "barış",
    "oguz": "oğuz",
    "yigit": "yiğit",
    "kagan": "kağan",
    "yilmaz": "yılmaz",
    "sahin": "şahin",
    "celik": "çelik",
    "aydin": "aydın",
    "ozturk": "öztürk",
    "dogan": "doğan",
    "kilic": "kılıç",
    "koc": "koç",
    "ozdemir": "özdemir",
    "ozkan": "özkan",
    "guler": "güler",
    "simsek": "şimşek",
    "cetin": "çetin",
}

ROOT_RE = re.compile(r"^([A-Za-z]+)(.*)$", re.DOTALL)


def _apply_case_pattern(original_root: str, corrected_root_lower: str) -> str:
    """corrected_root_lower'a, original_root'un büyük/küçük harf desenini uygular.

    Tüm harfler büyükse (VATANIM) tamamı büyük yapılır; ilk harf büyükse
    (Vatanim) sadece ilk harf büyütülür; aksi halde olduğu gibi (küçük) bırakılır.
    Not: Türkçe büyük I/İ ayrımı (ı -> I değil, ı -> I; i -> İ) burada basit
    tutulur çünkü kaynak kökler zaten sadece düz-ASCII/Title-case içeriyor.
    """
    if original_root.isupper():
        return corrected_root_lower.upper()
    if original_root[:1].isupper():
        return corrected_root_lower[:1].upper() + corrected_root_lower[1:]
    return corrected_root_lower


def main() -> None:
    lines = TARGET.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    added = 0

    for line in lines:
        m = ROOT_RE.match(line)
        if m:
            root, rest = m.group(1), m.group(2)
            corrected_lower = CORRECTIONS.get(root.lower())
            if corrected_lower:
                corrected_root = _apply_case_pattern(root, corrected_lower)
                corrected_line = corrected_root + rest
                if corrected_line != line:
                    output.append(corrected_line)
                    added += 1
        output.append(line)

    TARGET.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"[+] {added} adet doğru Türkçe karakterli satır eklendi (öncelikli, ASCII hali sonrasında korundu).")
    print(f"[+] Toplam satır sayısı: {len(output)}")


if __name__ == "__main__":
    main()
