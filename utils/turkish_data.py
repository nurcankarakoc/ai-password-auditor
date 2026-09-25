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
