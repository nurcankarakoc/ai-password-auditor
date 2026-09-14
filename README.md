# Cybzenor - Smart AI Password Auditor (SPA) 🛡️⚡

**Cybzenor**, hedefe yönelik OSINT istihbaratı, yapay zeka (NER/LLM) semantik analizi ve deterministik insan parola psikolojisi kurallarını birleştiren yeni nesil bir **Parola Denetim ve Güvenlik Testi (Pentest) Aracıdır**.

Geleneksel körleme (brute-force) wordlist'lerin aksine, hedefin psikolojisi, kulüp aidiyeti, ilişkileri, özel tarihleri ve hedef platformun **Parola Politikası (Password Policy)** kısıtlamalarına göre filtrelenmiş, yüksek öncelikli parola havuzları üretir.

---

## 🚀 Öne Çıkan Özellikler

- 🧠 **Yapay Zeka & Semantik NER:** Gemini LLM veya dahili çevrimdışı (Offline Regex NLP) motor ile serbest hedef metinlerinden yapılandırılmış profil (`TargetProfile`) çıkarımı.
- 🎯 **İnteraktif Parola Politikası (Password Policy):** Hedef sistemin (Active Directory, Instagram, Şirket Portalı) kurallarına göre (Min/Max uzunluk, Büyük/Küçük harf, Rakam, Özel Karakter) dinamik filtreleme.
- 👤 **İnsan Psikolojisi Odaklı Önceliklendirme:** `Ahmet123`, `Yilmaz1`, `Demir123!` gibi en yaygın insan alışkanlıklarını doğrudan en tepeye alan katmanlı skorlama (P1, P2, P3).
- 🛡️ **Kulüp ve Gürültü Zekası (Anti-Noise):** Hedef Fenerbahçeliyse listeye rakip kulüp yıllarının (`1903`, `1905`) sızmasını engeller; `20042004` gibi çifte tarih tekrarlarını otomatik ayıklar.
- 📈 **3.000 - 10.000+ Aday Kapasitesi:** En sıkı kurallarda dahi kaliteli, zengin ve hedefe odaklı geniş parola havuzu üretimi.
- ⚡ **Hafif ve Streaming (Akışkan):** RAM tüketimi sıfıra yakın (Python `generator / yield` mimarisi).
- 🔒 **Güvenlik Sigortası (Safety Controller):** HTTP 429 (Rate Limit), Hesap Kilitleme (423/Lockout) ve CAPTCHA tespitinde testi derhal durdurma.
- 📊 **Kıyaslama ve Raporlama (Benchmark Suite):** AI hedefli liste ile genel listeyi başarı oranı, süre ve verimlilik açısından kıyaslama.

---

## 🐧 Kali Linux Kurulumu

Projeyi Kali Linux üzerinde çalıştırmak son derece kolaydır:

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/KULLANICI_ADINIZ/ai-password-auditor.git
cd ai-password-auditor
```

### 2. Sanal Ortamı Oluşturun ve Paketleri Yükleyin
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

*(İsteğe Bağlı: Gemini AI kullanmak isterseniz)*
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 💻 Kullanım

### A. İnteraktif Konsol Arayüzü (Ana Menü)
Tüm özellikleri menü üzerinden adım adım kullanmak için:
```bash
python3 main.py
```
Menü Seçenekleri:
1. `[1] Wordlist Management` (Listeleme, filtreleme, inceleme)
2. `[2] AI Targeted Wordlist Generation` (Hedefli AI parola listesi üretimi)
3. `[3] Hybrid Wordlist Combiner` (AI listesi + Genel liste birleştirici)
4. `[4] Local Password Security Audit` (Yerel SHA-256 güvenlik denetimi)
5. `[5] Comparative Benchmark Suite` (Verimlilik ve kıyaslama raporu)

---

### B. Cybzenor Hızlı Terminal Komutları ⚡
Menüye girmeden doğrudan Kali terminalinden tek satırla:

```bash
# Kayıtlı hedef profillerini ve istihbarat kartlarını listele
python3 cybzenor.py targets

# Belirli bir hedefin en olası ilk 20 parolasını incele
python3 cybzenor.py view target_01 20

# Hedefin sonundaki Leetspeak mutasyonlarını incele
python3 cybzenor.py tail target_01 15

# Liste içinde kelime ara
python3 cybzenor.py search Pamuk target_01

# Hedefin detaylı dosya ve politika kartını gör
python3 cybzenor.py info target_01
```

---

## 🧪 Testleri Çalıştırma

Tüm birim ve entegrasyon testlerini çalıştırmak için:
```bash
python3 -m pytest tests/ -v
```
*(64 testin 64'ü de 1 saniyeden kısa sürede %100 geçer).*

---

## ⚠️ Yasal Uyarı (Legal Disclaimer)

Bu araç yalnızca **yasal penetrasyon testleri, siber güvenlik eğitimleri ve sistem yöneticilerinin kendi sistemlerinin parola direncini denetlemesi** amacıyla geliştirilmiştir. İzin alınmamış sistemler üzerinde kullanılması yasa dışıdır.
