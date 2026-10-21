# PDF AI Book & Slide Translator (EN ➔ TR) 🚀

<p align="center">
  <a href="README.md">🇬🇧 English Documentation</a> •
  <a href="README_TR.md"><b>🇹🇷 Türkçe Dokümantasyon</b></a>
</p>

[![Language: C++17](https://img.shields.io/badge/Language-C%2B%2B17-00599C.svg?style=flat&logo=c%2B%2B)](https://isocpp.org/)
[![Language: Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![UI: Obsidian Cyber-GUI](https://img.shields.io/badge/GUI-Obsidian%20Workstation-38BDF8.svg?style=flat)](#-modern-grafik-arayüz-obsidian-cyber-workstation)
[![Framework: PyTorch](https://img.shields.io/badge/PyTorch-CUDA%20%2F%20RTX%205080%20Ready-EE4C2C.svg?style=flat&logo=pytorch)](https://pytorch.org/)
[![Acceleration: OpenMP](https://img.shields.io/badge/Acceleration-OpenMP%20Multi--threading-green.svg)](https://www.openmp.org/)
[![Privacy: 100% Offline](https://img.shields.io/badge/Privacy-100%25%20Offline%20%26%20Air--Gapped-success.svg)](#-gizlilik-ve-güvenlik)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Akademik kitaplar, ders slaytları ve teknik makaleler için formülleri ve mizanpajı milimetrik koruyan, %100 yerel ve çevrimdışı çalışan hibrit (C++17 + Python) yapay zekâ çeviri iş istasyonu.**

---

<p align="center">
  <img src="assets/app_preview.png" alt="PDF AI Engine Pro Workstation" width="100%" />
</p>

---

## ⚡ Hızlı Başlangıç (Sıfır Yapılandırma & Tek Tıkla Kurulum)

Uygulama, sıfır yapılandırma ile (out-of-the-box) çalışacak şekilde tasarlanmıştır. Karmaşık ortam ayarlarıyla uğraşmadan hemen kullanmaya başlayabilirsiniz:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  0. ADIM:  Projeyi İndirin:                                                     │
│            GitHub sayfasındaki yeşil `<> Code` butonuna basıp `Download ZIP`    │
│            deyin ve klasöre çıkartın (veya `git clone` yapın).                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. ADIM:  Kurulum_Yap.bat dosyasına çift tıklayın.                            │
│            (Python sanal ortamı, PyTorch/CUDA kütüphaneleri ve çeviri modeli    │
│            otomatik olarak indirilir ve yerel diskinize kilitlenir.)            │
├─────────────────────────────────────────────────────────────────────────────────┤
│  2. ADIM:  Baslat.bat dosyasına çift tıklayın.                                 │
│            (Obsidian Cyber-Workstation masaüstü grafik arayüzü doğrudan açılır.)│
├─────────────────────────────────────────────────────────────────────────────────┤
│  3. ADIM:  "Seç..." butonuyla İngilizce PDF'inizi belirleyin ve                 │
│            "🚀 ÇEVİRİYİ BAŞLAT" butonuna tıklayın!                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

> 💡 **Not:** İlk kurulum tamamlandıktan sonra bilgisayarınızın **interneti tamamen kapalı olsa bile** çeviri motoru %100 yerel donanımınızla çalışır.

---

## 💻 Geliştiriciler & Komut Satırı Severler İçin (Manuel Başlatma)

Uygulamayı doğrudan terminal üzerinden yönetmek isterseniz:

### Windows (PowerShell / CMD)
```powershell
# 1. Sanal ortamı aktif edin
.\ai_env\Scripts\activate

# 2. Grafik Arayüzü başlatın:
python app_gui.py

# VEYA doğrudan komut satırından çeviri motorunu çalıştırın:
python pdf_bridge.py
```

### Linux / macOS
```bash
# 1. Sanal ortam oluşturup aktif edin
python3 -m venv ai_env
source ai_env/bin/activate

# 2. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 3. Arayüzü başlatın
python3 app_gui.py
```

---

## 🖥️ Modern Grafik Arayüz (Obsidian Cyber-Workstation)

[`app_gui.py`](app_gui.py) ile sunulan stüdyo arayüzü şu gelişmiş yeteneklere sahiptir:

* 📁 **Akıllı Belge Seçici:** Kaynak PDF'i ve çıktı yollarını belirleyin; sayfa sayısı ve dosya meta verileri anında listelenir.
* 👁️ **Canlı Çift Yönlü Sayfa Önizleme:** Çeviri esnasında veya sonrasında orijinal İngilizce sayfa ile çevrilmiş Türkçe sayfayı tek tıkla canlı karşılaştırın.
* 📊 **Canlı Donanım Telemetrisi:** Sistemdeki GPU/CPU mimarisini (RTX 5080 sm_120, CUDA çekirdekleri veya çok çekirdekli CPU) otomatik tanır ve durumunu gösterir.
* 🛡️ **Hava Boşluğu (Air-Gapped) Göstergesi:** %100 çevrimdışı çalışma kilidini ve sıfır veri sızıntısı protokolünü doğrular.
* 📝 **İki Dilli Karşılaştırma Masası (Bilingual Review):** Orijinal paragraf ile Türkçe çeviriyi blok blok yan yana sunar; doğrudan seçip kopyalayabilirsiniz.
* ⚡ **Canlı İlerleme Çubuğu ve Log Akışı:** OCR, formül maskeleme ve C++ mizanpaj adımlarını yüzdelik dilimlerle anlık olarak takip edin.

---

## 🛡️ Neden Bu Proje? (Geleneksel Çeviriler vs. PDF AI Engine)

<p align="center">
  <img src="assets/comparison_demo.png" alt="PDF AI Engine Before and After Comparison" width="100%" />
</p>

Standart çeviri araçları akademik ve teknik dokümanlarda mizanpajı ve denklemleri bozar:

| Özellik / Kriter | Standart Çeviri Araçları (Google Translate / DeepL) | 🚀 PDF AI Engine Pro (v14.0) |
| :--- | :--- | :--- |
| **Matematik ve Denklemler** | Formülleri metne çevirip bozar ($x^2 \to x2$, $r^{n-1} \to rn-1$) | 🛡️ **Unicode Üst/Alt İndis ve MTH Token Kalkanı** ile formülleri %100 korur |
| **Sayfa Mizanpajı & Tipografi** | Metin kutularını, tabloları ve grafik altı yazılarını kaydırır | ⚡ **C++17 OpenMP ve Dinamik Font Sığdırma** ile milimetrik yerleşim sağlar |
| **Zemin Rengi & Kontrast** | Koyu slaytlarda beyaz kutu yapıştırıp görseli bozar | 🎨 **Dış Halka Renk Örnekleme:** Koyu zemine beyaz, açık zemine koyu yazı basar |
| **Akademik Terminoloji** | Genel/sözlük çevirisi yapar (*Radix* $\to$ *Kök*) | 📚 **Bütünleşik Terim Sözlüğü:** *Radix Complement* $\to$ *Taban Tümleyeni* |
| **Gizlilik & Güvenlik** | Dokümanlarınızı harici bulut sunucularına yükler | 🔒 **%100 Çevrimdışı (Air-Gapped):** Hiçbir veri bilgisayarınızın dışına çıkmaz |
| **Donanım Optimizasyonu** | Donanım hızlandırması sınırlıdır | 🚀 **RTX 5080 (CUDA 12.8 / sm_120) Tensör Çekirdeği** + Çok çekirdekli CPU Fallback |
| **Çıktı Çeşitliliği** | Sadece tek bir PDF çıktısı verir | 📑 **3'ü 1 Arada Çıktı:** Seçilebilir PDF + Temiz TXT + İki Dilli Karşılaştırmalı TXT |

---

## 🏛️ Mimari ve İş Akışı (Architecture Workflow)

```mermaid
flowchart TD
    A[Girdi Belgesi: PDF] --> B{Belge Analizi ve Format Tespiti}
    
    B -->|Vektorel ve Dijital Metin| C[1. Tipografi ve Metin Ayristirma<br/>PyMuPDF: Font, Punto, Bounding Box]
    B -->|Taranmis Gorsel veya Resim| D[1. Adaptif OCR Katmani<br/>OpenCV ve Cift Gecisli Tesseract]
    
    C --> E[2. Matematik ve Indis Rekonstruksiyonu<br/>Alt ve Ust Simgelerin Tespiti]
    D --> E
    
    E --> F[3. Formul ve Denklem Maskeleme<br/>MTH Token Guvenlik Kalkani]
    F --> G[4. Akademik Terminoloji Sozlugu<br/>Sayisal Mantik ve Donanim Terimleri]
    G --> H[5. Noral Ceviri Motoru<br/>Helsinki-NLP MarianMT Cevrimdisi]
    H --> I[6. Formulleri Cozme ve Post-Edit<br/>Denklemlerin Birebir Geri Yuklenmesi]
    
    I --> J[7. C++17 AiEngine ve Python Auto-Fit<br/>OpenMP Paralel Bbox ve Punto Olcekleme]
    J --> K[8. Cerrahi Vektorel Render<br/>Zemin Rengi Eslestirme ve Kontrast Garantisi]
    
    K --> L[Cikti 1: Secilebilir Turkce PDF]
    K --> M[Cikti 2: Temiz Turkce TXT Metin]
    K --> N[Cikti 3: Iki Dilli Karsilastirmali TXT]
```

### 🔄 8 Aşamalı Uçtan Uca İşlem Hattı Detayı:

1. **📄 Belge Tipi Tespiti ve Düzen Analizi (DLA):**  
   Belgenin dijital vektörel metin mi yoksa taranmış fotoğraf/slayt mı olduğu sayfa bazında tespit edilir. Dijital metinler doğrudan PyMuPDF ile çıkarılırken; taranmış sayfalar OpenCV ve çift geçişli Tesseract OCR ile taranır.
2. **📐 Matematik ve İndis Rekonstrüksiyonu:**  
   Metin içindeki üst simgeler ($x^2, r^{n-1}$) ve alt simgeler ($a_0, N_1$) tespit edilerek Unicode seviyesinde korunur.
3. **🛡️ Formül ve Denklem Maskeleme (MTH Kalkanı):**  
   Denklemler ve saf matematik blokları çeviriye girmeden önce özel `MTH0X`, `MTH1X` jetonlarıyla maskelenir; modelin matematiksel sembolleri bozması engellenir.
4. **📚 Akademik ve Mühendislik Terim Sözlüğü:**  
   Sayısal tasarım, mantık devreleri ve bilgisayar mimarisi terimleri (*Radix Complement* $\to$ *Taban Tümleyeni*, *Discard end carry* $\to$ *Son eldeyi atın*) çeviri öncesinde kural tabanlı sözlükle standartlaştırılır.
5. **🧠 Nöral Çeviri Modeli:**  
   Helsinki-NLP MarianMT modeli tamamen çevrimdışı (offline) olarak yerel bellekten çalıştırılır ve cümle bazlı çeviri yapılır.
6. **🔓 Formül Geri Yükleme ve Doğrulama:**  
   Maskelenen tüm denklemler, orijinal matematiksel yapıları ve indisleri korunarak Türkçe çevirinin ilgili konumlarına geri yerleştirilir.
7. **⚡ C++17 AiEngine & Python Dinamik Font Adaptasyonu:**  
   Türkçenin İngilizceye kıyasla uzama katsayısı hesaplanır. C++17 OpenMP paralel motoru veya Python dinamik sığdırma algoritması ile font puntonu satır satır optimize edilerek sınırlayıcı kutulara (bbox) milimetrik sığdırılır.
8. **🎨 Cerrahi Vektörel Render ve Kontrast Garantisi:**  
   Orijinal sayfanın dış halka arka plan rengi piksellerden örneklenir. Eski İngilizce yazı silinir; arka plan koyuysa beyaz, açıksa koyu renkli metin katmanı basılarak fareyle seçilebilir, aranabilir ve kopyalanabilir Türkçe PDF üretilir.

---

## 📑 Üretilen 3'ü 1 Arada Çıktılar (Tri-Output System)

Bir belge işlendiğinde sistem eşzamanlı olarak 3 farklı formatta çıktı üretir:

1. **Kusursuz Türkçe PDF (`*_ULTIMATE.pdf`):** Orijinal mizanpajı koruyan, fareyle seçilebilir ve kopyalanabilir vektörel Türkçe PDF.
2. **Temiz Türkçe Transkript (`*_ULTIMATE.txt`):** Sayfa sayfa bölünmüş, metin ve formülleri içeren yalın Türkçe transkript.
3. **Karşılaştırmalı İnceleme Dosyası (`*_INCELEME.txt`):** Her paragrafın İngilizce orijinali ile Türkçe çevirisini yan yana sunan denetim kılavuzu.

---

## 📁 Proje Dizin Yapısı

```
pdf_ai_engine/
├── assets/                  # Önizleme ve karşılaştırma görselleri
│   ├── app_preview.png      # Obsidian Cyber Workstation GUI önizlemesi
│   └── comparison_demo.png  # Öncesi / Sonrası akademik karşılaştırma görseli
├── include/                 # C++ Başlık Dosyaları
│   ├── pdf_layout.h         # Belge düzeni ve sınırlayıcı kutu (BoundingBox) yapıları
│   ├── tensor.h             # Özel C++ Tensör ve matris optimizasyonları
│   └── tokenizer.h          # Yüksek hızlı kelime ayrıştırma arayüzü
├── src/                     # C++ Kaynak Kodları
│   ├── main.cpp             # OpenMP çok çekirdekli font adaptasyon motoru
│   ├── pdf_layout.cpp       # Düzen ve font hesaplama uygulamaları
│   ├── tensor.cpp           # Tensör çarpım mantığı
│   └── tokenizer.cpp        # C++ tokenizer uygulaması
├── app_gui.py               # Obsidian Cyber-Workstation masaüstü grafik arayüzü
├── pdf_bridge.py            # Ana yapay zekâ, OCR, mizanpaj ve render iş motoru
├── export_model.py          # MarianMT model ağırlıklarını Float32 ikili (.bin) formata dönüştürücü
├── Kurulum_Yap.bat          # Windows için tek tıkla otomatik kurulum sihirbazı
├── Baslat.bat               # Windows için tek tıkla grafik arayüz başlatıcı
├── CMakeLists.txt           # C++ projesi derleme konfigürasyonu
├── requirements.txt         # Gerekli Python kütüphaneleri
├── Giris.txt                # Hızlı komut referansı
├── LICENSE                  # MIT Lisansı
├── README.md                # Global İngilizce dokümantasyon
└── README_TR.md             # Türkçe dokümantasyon
```

---

## ⚙️ C++ AiEngine Motorunu Derleme (İsteğe Bağlı)

```bash
mkdir build
cd build
cmake ..
cmake --build . --config Release
cd ..
```

> ℹ️ **Not:** Bilgisayarınızda CMake veya C++ derleyicisi olmasa bile sistem durmaz; dahili Python dinamik font adaptasyon motoru otomatik devreye girer.

---

## ❓ Sıkça Sorulan Sorular (SSS)

<details>
<summary><b>1. İnternetim yokken bu program çalışır mı?</b></summary>
Evet! <code>Kurulum_Yap.bat</code> çalıştırıldığında gerekli çeviri modeli yerel diskinize kaydedilir. Sonrasında bilgisayarınızın ağ bağlantısını tamamen kesseniz bile program %100 çevrimdışı çalışır.
</details>

<details>
<summary><b>2. NVIDIA ekran kartım yok, programı çalıştırabilir miyim?</b></summary>
Kesinlikle evet. Program donanımınızı otomatik algılar. NVIDIA GPU bulamazsa kilitlenmez; çok çekirdekli işlemcinizi (CPU Multi-threading) devreye sokarak işlemi başarıyla tamamlar.
</details>

<details>
<summary><b>3. Taranmış slaytlarda ve koyu temalarda çalışır mı?</b></summary>
Evet. Çift geçişli Tesseract OCR ve adaptif görüntü filtreleme katmanı sayesinde hem beyaz zeminli hem de koyu temalı slaytları yüksek doğrulukla okuyup çevirir.
</details>

<details>
<summary><b>4. Kitaplardaki matematik formülleri bozulur mu?</b></summary>
Hayır. Gelişmiş MTH Token Kalkanı, matematik denklemlerini ve üst/alt indisleri çeviri öncesinde kilitler ve çeviri sonrasında orijinal yapısında geri yükler.
</details>

---

## 🔒 Gizlilik ve Güvenlik

* Bu yazılım **tamamen yerel ve kapalı devre (Air-Gapped)** çalışır.
* Belgeleriniz veya kişisel verileriniz hiçbir koşulda harici bir sunucuya aktarılmaz.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak lisanslanmıştır.
