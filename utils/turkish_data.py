"""
Cybzenor - Türkiye'ye Özgü Paylaşımlı Statik Veriler
Şehir/plaka ve kulüp kuruluş yılı gibi, hem AI çıkarım motorunun (ai/provider_cloud_base.py)
hem de main.py'deki yapılandırılmış profil giriş adımlarının ortak kullandığı sözlükler.
"""

TR_CITY_PLAKA = {
    'istanbul': '34', 'ankara': '06', 'izmir': '35', 'bursa': '16',
    'antalya': '07', 'adana': '01', 'trabzon': '61', 'konya': '42',
    'eskisehir': '26', 'kocaeli': '41', 'gaziantep': '27',
}
TR_PLAKA_CITY = {plaka: city.capitalize() for city, plaka in TR_CITY_PLAKA.items()}

# Anahtar kelime -> kuruluş yılı. RankingEngine'in kendi anlamsal kök motorundaki
# (core/ranking_engine.py, ai/provider_cloud_base.py::_generate_roots_via_heuristic)
# takım-yıl eşleşmeleriyle tutarlı tutulmalıdır.
TR_CLUB_FOUNDING_YEARS = {
    'besiktas': '1903', 'bjk': '1903',
    'fenerbahce': '1907', 'fener': '1907', 'fb': '1907',
    'galatasaray': '1905', 'gs': '1905',
    'trabzonspor': '1967', 'ts': '1967',
    'bursaspor': '1963',
}

# Kulüp -> onunla ilişkili sembol/kısaltma/yıl kümesi. _generate_roots_via_heuristic'teki
# team_affinity ile aynı veriden türetilmiştir; ayrıca küçük yerel modelin, prompttaki
# "Beşiktaşlıysa 1903/bjk ekle" gibi ÖRNEK kuralları profilde o takım hiç geçmese bile
# köklere sızdırmasına (papağan gibi tekrarlamasına) karşı filtrelemede kullanılır
# (bkz. ai/provider_cloud_base.py::_filter_irrelevant_club_references).
TR_CLUB_SYMBOLS = {
    'besiktas': {'bjk', '1903', 'kartal', 'karakartal'},
    'bjk': {'besiktas', '1903', 'kartal'},
    'fenerbahce': {'fb', '1907', 'fener', 'kanarya'},
    'fener': {'fb', '1907', 'fenerbahce'},
    'galatasaray': {'gs', '1905', 'cimbom', 'aslan'},
    'gs': {'galatasaray', '1905', 'aslan'},
    'trabzonspor': {'ts', '1967', 'trabzon', 'firtina'},
    'bursaspor': {'bursa', '1963', 'timsah'},
}
