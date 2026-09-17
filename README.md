# Cybzenor - Akıllı Hedefli Parola Denetim ve Güvenlik Araştırma Framework'ü 🛡️⚡

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Linux | Windows | macOS](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-teal.svg)]()
[![Tests: 67/67 Passed](https://img.shields.io/badge/tests-67%2F67%20passed-brightgreen.svg)]()

> **Yeni Başlayanlar İçin Özet:**  
> Klasik parola kırma araçları, içinde milyonlarca rastgele yabancı kelime olan devasa dosyalar (örn: `rockyou.txt`) kullanarak saatlerce boşuna bekletir.  
> **Cybzenor** ise gerçek insan davranışlarını temel alır: İnsanlar parolalarını sevdiklerinin ismi, tuttukları takım, evcil hayvanları ve doğum yıllarını birleştirip sonuna `123` veya `!` koyarak oluştururlar.  
> Cybzenor, hedef hakkındaki birkaç temel bilgiyi yapay zeka ve psikolojik kurallarla işleyerek **hedefe özel nokta atışı bir parola havuzu (wordlist)** üretir ve sisteminizin bu kombinasyonlara karşı ne kadar dirençli olduğunu **saniyede 1.000.000+ yerel hash hızıyla** denetler.

---

## 📑 İçindekiler
1. [Kurulum (3 Adımda Hızlı Başlangıç)](#-kurulum-3-adımda-hızlı-başlangıç)
2. [Adım Adım Kullanım Senaryoları](#-adım-adım-kullanım-senaryoları)
   - [Senaryo 1: Hedefe Özel Wordlist Üretmek](#senaryo-1-hedefe-özel-wordlist-üretmek-menü-2)
   - [Senaryo 2: Üretilen Şifreleri Hızlıca İncelemek](#senaryo-2-üretilen-şifreleri-hızlıca-incelemek-tek-satır-komutlar)
   - [Senaryo 3: Yerel Parola Güvenlik Denetimi (Hash Audit Engine)](#senaryo-3-yerel-parola-güvenlik-denetimi-hash-audit-engine-menü-4)
3. [Neden Düz Metin Şifre Yerine Hash Denetliyoruz?](#-neden-düz-metin-şifre-yerine-hash-denetliyoruz)
4. [Sık Karşılaşılan Sorular ve Çözümler (SSS)](#-sık-karşılaşılan-sorular-ve-çözümler-sss)
5. [Testleri Çalıştırma](#-testleri-çalıştırma)
6. [Yasal ve Etik Sorumluluk](#️-yasal-ve-etik-sorumluluk)

---

## 🚀 Kurulum (3 Adımda Hızlı Başlangıç)

### 🐧 Kali Linux / Ubuntu / Debian Üzerinde

Terminalinizi açın ve sırasıyla şu komutları yapıştırın:

```bash
# 1. Projeyi bilgisayarınıza indirin ve klasöre girin
git clone https://github.com/nurcankarakoc/ai-password-auditor.git
cd ai-password-auditor

# 2. Sanal ortam (venv) oluşturun ve aktif edin
python3 -m venv venv
source venv/bin/activate

# 3. Gerekli kütüphaneleri yükleyin
pip install --upgrade pip
pip install -r requirements.txt
```

### 🪟 Windows Üzerinde

PowerShell veya Komut Satırını açın:

```powershell
git clone https://github.com/nurcankarakoc/ai-password-auditor.git
cd ai-password-auditor
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

*(İsteğe Bağlı: Google Gemini Yapay Zeka anahtarınız varsa sisteme tanıtabilirsiniz; **yoksa da sorun değil**, araç dahili çevrimdışı NLP motoruyla %100 çalışır):*
```bash
export GEMINI_API_KEY="AIzaSy..."
```

---

## 🎮 Adım Adım Kullanım Senaryoları

Programı başlatmak için terminale şunu yazmanız yeterlidir:

```bash
python3 main.py
```

Ekrana Cybzenor ana operasyon menüsü gelecektir:

```text
================================================================================
   ____                      _     ____                                    _    
  / ___| _ __ ___   __ _ _ _| |_  |  _ \ __ _ ___ _____      _____  _ __ __| |   
  \___ \| '_ ` _ \ / _` | '__| __| | |_) / _` / __/ __\ \ /\ / / _ \| '__/ _` |   
   ___) | | | | | | (_| | |  | |_  |  __/ (_| \__ \__ \\ V  V / (_) | | | (_| |   
  |____/|_| |_| |_|\__,_|_|   \__| |_|   \__,_|___/___/ \_/\_/ \___/|_|  \__,_|   
                                  AUDITOR                                       
================================================================================
  [1] Varsayılan Wordlist İşlemleri (Default Wordlist Operations)
  [2] Yapay Zeka Hedefli Liste Üretimi (AI Targeted Wordlist)
  [3] Hibrit Wordlist Birleştirici (Hybrid Wordlist Generation)
  [4] Yerel Hash Denetim Motoru (Local Hash Audit Engine)
  [5] Canlı Login Ekranı Denetimi (Online Login Audit) [Sadece Yetkili Hedefler]
  [6] Kıyaslama ve Performans Analizi (Benchmark Module)
  [7] Çıkış (Exit)
```

---

### Senaryo 1: Hedefe Özel Wordlist Üretmek (Menü [2])

1. Menüde `2` yazıp **Enter**'a basın.
2. Karşınıza hedef hakkında bilgi toplayan sorular gelecektir.  
   *(İpucu: Hiçbir soru zorunlu değildir; bilmediğiniz kısımları boş bırakıp doğrudan Enter'a basabilirsiniz).*
   - **İsimler:** `Ahmet, Ayşe, Pamuk` (hedef kişi, eşi, çocuğu, evcil hayvanı vb.)
   - **Tarihler:** `1995, 2021` (doğum yılı, evlilik yılı vb.)
   - **Şehir/Plaka:** `İstanbul, 34`
   - **İlgi Alanları/Takım:** `Fenerbahçe` (Takım zekası devreye girer; rakip kulüp yıllarını temizler!)
3. **Parola Politikası (Password Policy) Belirleme:**  
   Hedef sistemin kuralları sorulur (Örn: En az 8 karakter, 1 büyük harf, 1 rakam, 1 özel karakter).
   - Bu sayede sistem, hedef sistemin kabul etmeyeceği gereksiz tüm çöpleri eler.
4. **Sonuç:**  
   Saniyeler içinde `wordlists/generated/` klasörüne hedefe odaklı 5.000 ila 25.000+ kaliteli parola adayı üretilir ve öncelik sırasına göre dizilir.

---

### Senaryo 2: Üretilen Şifreleri Hızlıca İncelemek (Tek Satır Komutlar)

Ana menüye girmeden doğrudan terminalden hızlıca hedefleri inceleyebilirsiniz:

```bash
# 1. Mevcut üretilmiş hedef profillerini listele
python3 cybzenor.py targets

# 2. Üretilen hedefin en olası ilk 20 şifresini ekranda gör
python3 cybzenor.py view target_01 20

# 3. Listenin sonundaki Leetspeak (harf-rakam dönüşümlü) şifreleri gör
python3 cybzenor.py tail target_01 15

# 4. Liste içinde belirli bir kelimeyi ara (Örn: 'Pamuk' geçen parolalar)
python3 cybzenor.py search Pamuk target_01

# 5. Hedefin parola politikası ve dosya boyut kartını incele
python3 cybzenor.py info target_01
```

---

### Senaryo 3: Yerel Parola Güvenlik Denetimi (Hash Audit Engine) (Menü [4])

Elinizde bir kullanıcının veya sistemin parola özeti (SHA-256 Hash'i) olduğunda, ürettiğiniz wordlist'in bu parolayı yakalayıp yakalayamayacağını test edersiniz:

1. `main.py` menüsünden **`4`** seçin.
2. **`2`** seçin (*Manuel Hedef SHA-256 Hash'i Gir*).
3. Test etmek istediğiniz hash değerini yapıştırın.
4. Ekranda listelenen wordlist'lerden incelemek istediğiniz listenin numarasını seçin.
5. **Sonuç:**  
   Motor adayları bellekte saniyede **1.000.000+'dan fazla** hızla tarar ve eşleştiğinde parolanın açık halini, kaçıncı denemede bulunduğunu ve geçen süreyi raporlar:

```text
------------------------
  DENETİM SONUÇ RAPORU
------------------------
[+] PAROLA BAŞARIYLA TESPİT EDİLDİ (MATCH)!
 • Açık Parola       : Denizceren34.
 • Bulunduğu Sıra    : 142. denemede
 • Test Edilen Aday  : 142
 • Geçen Süre        : 0.0008 saniye
 • Ortalama Hız      : 1,320,400 hash/sn
```

---

## 🔒 Neden Düz Metin Şifre Yerine Hash Denetliyoruz?

Yeni başlayanların en sık sorduğu soru: *"Neden direkt şifreyi yazıp aramıyoruz da SHA-256 hash'i giriyoruz?"*

1. **Sistemler Şifreleri Açık Metin Saklamaz:** Hiçbir modern işletim sistemi veya web sitesi parolaları açık olarak tutmaz. Veritabanlarında şifrelerin yalnızca tek yönlü matematiksel özetleri (**Hash**) saklanır.
2. **Gerçek Hayat Denetimleri:** Bir sızma testinde (pentest) elinize açık şifreler geçmez; sistemin parola hash dosyası geçer. Göreviniz, şirket çalışanlarının şifrelerinin tahmin edilebilir olup olmadığını bu hash'ler üzerinden kanıtlamaktır.
3. **Eğer açık şifreyi bilseydik:** Basit bir kelime aramasından ibaret olurdu; kriptografik bir güvenlik denetimi olmazdı.

---

## ❓ Sık Karşılaşılan Sorular ve Çözümler (SSS)

### S: `onulmaz: bir git deposu değil` (not a git repository) hatası alıyorum. Ne yapmalıyım?
> **Cevap:** Terminalde yanlış dizindesiniz demektir (muhtemelen `~` ana klasöründesiniz).  
> Çözüm: `cd ~/ai-password-auditor` yazarak proje klasörünün içine girip öyle `git pull` yapın.

### S: Gemini API Anahtarı (API Key) almak zorunda mıyım?
> **Cevap:** Hayır, kesinlikle zorunlu değildir. API anahtarı girmediğinizde Cybzenor dahili **Offline Regex NLP ve Heuristic Motoru**nu kullanır. Bu motor internete ihtiyaç duymadan hedefin takımları, isimleri ve ilişkilerini yüksek doğrulukla ayrıştırır.

### S: Ürettiğim wordlist'ler ve hedef bilgileri GitHub'a yüklenir mi?
> **Cevap:** Hayır. `.gitignore` dosyamızda `wordlists/generated/` ve `logs/` tanımlıdır. Ürettiğiniz hiçbir özel liste veya hedef verisi asla GitHub'a gitmez; yalnızca sizin bilgisayarınızda yerel olarak kalır.

---

## 🧪 Testleri Çalıştırma

Kod tabanının doğruluğunu ve güvenilirliğini teyit etmek için hazırlanmış 64 kapsamlı birim testi bulunmaktadır:

```bash
python3 -m pytest tests/ -v
```

*(Tüm testler yaklaşık 1-2 saniye içinde %100 yeşil olarak tamamlanır).*

---

## ⚠️ Yasal ve Etik Sorumluluk

Bu yazılım yalnızca **yetkili penetrasyon testleri, siber güvenlik eğitimleri, akademik araştırmalar ve sistem yöneticilerinin kendi sistemlerinin parola politikası direncini ölçmesi** amacıyla geliştirilmiştir.  
Yazılı izni veya yetkisi bulunmayan sistemler üzerinde parola denetimi yapmak veya yetkisiz erişim sağlamaya çalışmak yasa dışıdır. Doğabilecek tüm hukuki sorumluluk kullanıcıya aittir.
