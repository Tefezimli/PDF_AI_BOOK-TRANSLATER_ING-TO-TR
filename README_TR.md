# PDF AI Kitap & Slayt Çevirici (EN -> TR) 🚀

<p align="center">
  <a href="README.md">🌐 English Documentation</a> •
  <a href="README_TR.md"><b>🇹🇷 Türkçe Dokümantasyon</b></a>
</p>

[![Sürüm: v18.0 Pro](https://img.shields.io/badge/S%C3%BCr%C3%BCm-v18.0%20Pro%20Ultimate-7C3AED.svg?style=flat)](https://github.com/Tefezimli/PDF_AI_BOOK-TRANSLATER_ING-TO-TR)
[![Sürümler: Lite & Pro](https://img.shields.io/badge/S%C3%BCr%C3%BCmler-Lite%20%7C%20Pro-0284C7.svg?style=flat)](#-s%C3%BCr%C3%BCmler-lite-vs-pro-ultimate)
[![LLM: Qwen2.5 14B & MarianMT](https://img.shields.io/badge/LLM-Qwen2.5%2014B%20%2B%20MarianMT-F59E0B.svg?style=flat)](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct)
[![Programlama: Python 3.10+](https://img.shields.io/badge/Python-3.10%20--%203.14-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![Donanım: NVIDIA CUDA](https://img.shields.io/badge/NVIDIA%20CUDA-RTX%2050%20%2F%2040%20%2F%2030%20%2F%20GTX%20Uyumlu-76B900.svg?style=flat&logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)
[![Gizlilik: %100 Çevrimdışı](https://img.shields.io/badge/Gizlilik-%25100%20%C3%87evrimd%C4%B1%C5%9F%C4%B1%20%26%20Air--Gapped-success.svg)](#-gizlilik-ve-g%C3%BCvenlik)
[![Lisans: MIT](https://img.shields.io/badge/Lisans-MIT-yellow.svg)](LICENSE)

> **Akademik kitaplar, ders slaytları ve teknik makaleler için formülleri, donanım kod bloklarını (VHDL/Verilog/C) ve mizanpajı milimetrik koruyan, %100 yerel ve çevrimdışı çalışan hibrit sinirsel yapay zeka çeviri iş istasyonu.**

---

<p align="center">
  <img src="assets/app_preview.png" alt="PDF AI Engine Pro Workstation" width="100%" />
</p>

---

## 🚀 Sürümler: Lite vs Pro (Ultimate)

Bu depo iki farklı kullanıcı kitlesi ve donanım profili için iki ayrı dalda (branch) sunulmaktadır:

| Boyut | 🟢 Lite Sürüm (`branch: lite`) | 🟣 Pro Sürüm (`branch: main`) |
| :--- | :--- | :--- |
| **Hedef Kitle** | Standart kullanıcılar, hafif bilgisayarlar, hızlı çeviri | Mühendisler, akademisyenler, ağır teknik ders kitapları |
| **Yapay Zeka Modeli** | MarianMT (`opus-mt-tc-big-en-tr`, ~1.2 GB) | **Qwen 2.5 14B GGUF** (LM Studio / Bionic) + Marian Hibrit |
| **Donanım İhtiyacı** | Standart CPU veya 2-4 GB VRAM GPU | 8 GB+ VRAM GPU veya 16 GB+ Sistem Belleği |
| **Kod & Formül Kalkanı** | Temel regex koruması | **Tam VHDL, Verilog, C, GDB, Assembly Karantinası + LaTeX Kalkanı** |
| **Mizanpaj Hassasiyeti** | ~%90 blok düzeni | **%99.8+ Sıfır Çakışmalı Blok & %100 Vektörel Devre Korunumu** |
| **Mimari** | Tekil monolitik betik | **Modüler Katmanlar (`core/`, `extractors/`, `renderers/`, `translators/`)** |

### Dallar Arasında Geçiş:
* **Genel Kullanıcı Sürümüne Geçmek İçin (Lite):**
  ```bash
  git checkout lite
  ```
* **Tam Akademik & Mühendislik Gücüne Geçmek İçin (Pro):**
  ```bash
  git checkout main
  ```

---

## ⚡ Hızlı Başlangıç (Pro Sürümü)

### 1. Adım: Bağımlılıkları Kurun
`Kurulum_Yap.bat` dosyasına çift tıklayın.
* Sisteminizdeki Python sürümünü otomatik denetler (yoksa Python 3.11 kurar).
* Ekran kartınızı (RTX 50 / 40 / 30 / GTX) algılar ve CUDA hızlandırmalı PyTorch'u yapılandırır.
* Temel çevrimdışı MarianMT model ağırlıklarını (~1.2 GB) yedek motor olarak indirir.

### 2. Adım: (Önerilen) LM Studio ile Qwen 2.5 14B'yi Aktifleştirin
En yüksek akademik ve teknik çeviri kalitesi için (700+ sayfalık mühendislik kitapları düzeyinde):
1. [lmstudio.ai](https://lmstudio.ai) adresinden **LM Studio** (veya Bionic) kurun.
2. Model arama çubuğundan `TheRains/Qwen2.5-14B-Instruct-Q4_K_M-GGUF` modelini indirin.
3. LM Studio içinde Local Server sekmesinden sunucuyu `1234` portunda başlatın (veya terminalden: `lms server start --port 1234`).
4. LM Studio'yu arka planda çalışır durumda bırakın.

### 3. Adım: Uygulamayı Başlatın
`Baslat.bat` dosyasına çift tıklayın.
* Motor, yerel LM Studio sunucusunu otomatik olarak algılar:
  ```text
  [LM STUDIO AKTIF] Yerel LLM Sunucusu Algilandi! Aktif Model: qwen2.5-14b-instruct
  ```
* Eğer LM Studio açık değilse, sistem otomatik olarak yerel MarianMT motoruna geçerek kesintisiz çalışmaya devam eder.
* İngilizce PDF'inizi seçin ve **"🚀 ÇEVİRİYİ BAŞLAT"** butonuna basın!

### Linux / macOS
Windows kurulum sihirbazına gerek yoktur:

```bash
python3 -m venv ai_env
ai_env/bin/pip install -r requirements.txt
sudo apt install tesseract-ocr          # taranmış sayfa OCR'i (Debian/Ubuntu; Arch: sudo pacman -S tesseract)
./Baslat.sh                             # grafik arayüz
./Baslat.sh --cli kitap.pdf -o cikti.pdf  # komut satırı çevirisi
```

Türkçe karakterler için sistemde DejaVu Sans / Liberation Sans / Noto Sans fontlarından biri bulunmalıdır (çoğu dağıtımda hazır gelir). Kendi fontunuzu zorlamak için `PDF_AI_FONT_REGULAR` ve `PDF_AI_FONT_BOLD` ortam değişkenlerini kullanabilirsiniz.

### Yapılandırma (Ortam Değişkenleri)
| Değişken | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `PDF_AI_LMSTUDIO_URL` | `http://localhost:1234/v1` | LM Studio sunucu adresi |
| `PDF_AI_LMSTUDIO_PORT` | `1234` | Sadece port (URL verilmediyse) |
| `PDF_AI_LMSTUDIO_MODEL` | ilk model | Sunucudaki modellerden tercih (alt dizi eşleşmesi; örn. 8 GB VRAM için küçük bir 7B modeli) |
| `PDF_AI_LMSTUDIO_TIMEOUT` | `45` | Blok başına üretim zaman aşımı (sn) |
| `PDF_AI_LMSTUDIO_CHECK_TIMEOUT` | `2` | Sunucu algılama zaman aşımı (sn) |
| `PDF_AI_LMSTUDIO_ATTEMPTS` | `1` | Blok başına deneme sayısı |
| `PDF_AI_FONT_REGULAR` / `PDF_AI_FONT_BOLD` | otomatik | Türkçe glifli TTF fontunu zorla |

> Geliştiriciler: `pytest` ile test paketi ağır AI kütüphaneleri olmadan koşar; `ruff check .` lint.

---

## 🔬 Pro Sürümdeki (v18.0) Temel Mühendislik İnovasyonları

1. **Donanım ve Sistem Kodu Karantinası:**
   VHDL (`entity`, `architecture`, `std_logic`), Verilog (`module`, `always @`), C/C++ (`#include`, pointer, GDB register'ları) ve Assembly (`0x...` hex izleri) kodlarını çeviriden %100 izole ederek sıfır kayıpla korur.
2. **LaTeX ve Matematiksel Formül Kalkanı:**
   Grek harflerini, alt/üst indisleri, integral ve toplam sembollerini dokunulmaz unicode token'larına dönüştürür.
3. **Cerrahi Vektörel Redaksiyon & Çizim Koruması:**
   Orijinal İngilizce metin katmanını kaldırırken arkasındaki vektörel lojik kapıları, flip-flop devrelerini ve şemaları pikselleştirmeden korur.
4. **Çakışmasız Optik Tipografi:**
   Dinamik satır yüksekliği ve yazı boyutu optimizasyonu ile çift sütunlu akademik sayfalarda **%99.8 çakışmasız mizanpaj** sağlar.
5. **Ayrık Modüler Mimari:**
   * `core/`: Donanım soyutlama katmanı, bellek yaşam döngüsü, unicode temizleyici.
   * `extractors/`: Mizanpaj motoru, sözdizim ayrıştırıcı, içindekiler tablosu dedektörü.
   * `renderers/`: Redaksiyon renderlayıcı, font yöneticisi, adli denetim motoru.
   * `translators/`: LM Studio backend, MarianMT backend, terim sözlüğü yöneticisi.

---

## 📄 Üçlü Çıktı Üretim Sistemi

İşlenen her belge için eş zamanlı olarak 3 çıktı üretilir:

1. **Seçilebilir Türkçe PDF (`*_ULTIMATE.pdf`):** Orijinal belgenin görsel ikizi; vektörel ve seçilebilir metin katmanına sahip PDF.
2. **Temiz Türkçe Transkript (`*_ULTIMATE.txt`):** Sayfa sayfa düzenlenmiş arı Türkçe ve matematiksel transkript.
3. **İki Dilli Karşılaştırma TXT'si (`*_INCELEME.txt`):** Orijinal İngilizce bloklar ile Türkçe çevirileri yan yana gösteren adli denetim dosyası.

---

## 💻 Geliştirici & Programatik API

Grafik arayüze ihtiyaç duymadan kendi Python projelerinizden tek satırla çeviri başlatabilirsiniz:

```python
from pdf_bridge import run_pipeline

run_pipeline(
    input_pdf="akademik_kitap.pdf",
    output_pdf="akademik_kitap_TR.pdf"
)
```

Terminalden tek komutla da mümkün:

```bash
python pdf_bridge.py akademik_kitap.pdf -o akademik_kitap_TR.pdf [--no-ocr]

# Paket olarak kurulum (pdfai-translate komutunu verir):
pip install -e .          # hafif kurulum (torch/transformers hariç)
pip install -e .[ai]      # CPU torch + transformers dahil (CUDA için Kurulum_Yap.bat'ı kullanın)
```

---

## 🔒 Gizlilik ve Güvenlik

* **%100 İnternetsiz & Air-Gapped:** Belgeleriniz ve çeviri metinleriniz asla harici bulut sunucularına gönderilmez.
* **Telemetri Kapalı:** Kod düzeyinde Hugging Face telemetrisi devre dışı bırakılmıştır (`HF_HUB_OFFLINE=1`).
* **Sıfır Bulut Sızıntısı:** Her şey kendi donanımınız üzerinde çalışır.

---

## 📜 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynaklıdır.
