# Changelog

Bu dosyadaki önemli değişiklikler kayıt altına alınır.
Format [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) esnekliğinde, sürümleme [SemVer](https://semver.org/) mantığındadır.

## [18.1.1] — 2026-10-28

### Düzeltildi (2026-10-28 kod incelemesinin bulguları)
- `--pages 1-1000000000` gibi girdiler RAM'i kilitlemiyordu → aralıklar toplam sayfaya clamp'lenir.
- Kısmi `--pages` koşusu tüm-kitap checkpoint'ini siliyordu → artık yalnız tüm sayfalar işlendiğinde silinir.
- Önbellek yazımı atomik (tmp + os.replace): çökme anında yarım JSON önbelleği sıfırlamıyor.
- Şifreli/bozuk PDF girdileri `PDFInputError` ile net tek satır hata verir; `run_pipeline` dokümanı her durumda kapatır (fd sızıntısı yok).
- LM Studio: `finish_reason=length` yanıtları reddedilir (kesik çeviri asla kabul/önbelleklenmez); `max_tokens` girdi uzunluğuna göre ölçeklenir.
- Önbellek anahtarları motor etiketlidir (`llm|`/`opus|`): Opus-MT yedek çevirileri gelecekteki LLM koşularını gölgemez.
- **Adli denetim devrede:** LLM bir `⟦CODE_X⟧` maskesini silerse çeviriye otomatik geri eklenir; ciddi eksik çeviride orijinal metne dönülür (önceden ölü koddu).
- Geçersiz `PDF_AI_FONT_BOLD` düzgün biçimde regular fonta düşer; cv2 eksikse OCR tek uyarıyla atlanır (çökme yok).
- TOC sayfa numarası deseni katı roma rakamı kullanır ("civil"/"mild" sayfa no sanılmaz).
- E-posta adresleri `@` onarım kurallarından etkilenmez.
- SECURITY.md ağ iddiaları düzeltildi (ilk kurulumda HF indirmesi; uzak LM Studio URL uyarısı).

### Değişti
- Paket bağımlılığı `opencv-python` → `opencv-python-headless` (CLI/headless kullanım için yeterli, Qt çekmez).

## [18.1.0] — 2026-10-28

### Eklendi
- **Checkpoint / Resume:** mizanpaj analizi sayfa sayfa `build/checkpoints/` altına yazılır; işlem çökse bile yeniden başlatmada kaldığı sayfadan devam eder. Çeviri önbelleği artık her sayfada diske floşlanır (en kötü kayıp: 10 sayfa → 1 sayfa). CLI: `--fresh`.
- **Kısmi çeviri (`--pages 1-10`):** büyük kitaplarda yalnız seçili sayfalar çevrilir; seçilmeyenler orijinal kalır, çıktı `<ad>_p<aralik>_ULTIMATE.pdf` adını alır.
- **Ortam tanılama (`--doctor`):** bağımlılıklar, Tesseract, Türkçe font, LM Studio erişimi + modeller, önbellek sağlığı ve checkpoint raporu. Hafif kurulumda da çalışır.
- **Çeviri kalitesi değerlendirme seti (`--eval`):** 12 altın vaka; deterministik terminoloji zinciri offline sınanır, LM Studio açıksa canlı LLM de (maske kalıntısı, yasak gaf terimleri, uzunluk oranı) sınanır.
- **Yapılandırılmış ilerleme kanalı:** `run_pipeline(..., progress_cb=...)` → GUI artık gerçek sayfa-bazlı yüzde gösterir (konsol kazıması yedek olarak kaldı).
- **LM Studio yapılandırması:** `PDF_AI_LMSTUDIO_URL/_PORT/_MODEL/_TIMEOUT/_CHECK_TIMEOUT/_ATTEMPTS` (8 GB VRAM'de küçük modelle yerel smoke test mümkün).
- **GUI Ayarlar sekmesi:** LM Studio URL/port/model, OCR aç/kapa, sayfa aralığı ve "sıfırdan başla" seçenekleri arayüzden yönetilir; `build/gui_settings.json` içinde kalıcıdır.
- **Linux/macOS desteği:** `Baslat.sh`, platform bağımsız Türkçe font seçimi (DejaVu/Liberation/Noto + `PDF_AI_FONT_REGULAR/_BOLD`), `xdg-open`/`open` entegrasyonu.
- **Paketleme:** `pyproject.toml` (pdf-ai-translator); `pip install -e .` hafif kurulum, `.[ai]` tam AI stack'i, `pdfai-translate` konsol komutu. Torch/transformers bilinçli olarak extra'da (CUDA kurulum akışı bozulmaz).
- **CI:** GitHub Actions'ta pytest matrisi (Python 3.10/3.12/3.14) + ruff lint.
- **Test paketi:** 101 test (sanitizer, formalizm karantinası, TOC, adli denetçi, önbellek, LM Studio istemcisi, checkpoint, tanılama, değerlendirme seti, CLI, ayarlar).

### Değişti
- Kod/formül sınıflandırıcıda iki karantina açığı kapatıldı: VHDL yapı satırları (`architecture rtl of counter is`) ve terminal istemli satırlar (`$ nmap ...`) artık kod olarak karantinaya alınır.
- `requirements.txt` tüm bağımlılıklara üst sürüm sınırı aldı; `Kurulum_Yap.bat` akışı değişmedi.
- Önbellek dosyası kompakt JSON'a geçti.

### Kaldırıldı
- Bayat öz-kurulum betikleri (`adim1-5_*.py`, ~6.100 satır; içerikleri git tarihçesinde).
- C++ AiEngine varsayılan olarak devre dışı (`CPP_LAYOUT_ENGINE_ENABLED=False`): `layout_out.txt` çıktısı hiçbir Python koduna bağlı değildi; bağlı olana dek kapalı kalır.

### Düzeltildi
- Unicode temizleyicide tekrarlanan parantez dönüşüm zincirleri tek yardımcıya indirildi; `locals()`/walrus/`globals()` hileleri, kullanılmayan import'lar ve ölü sabitler temizlendi (davranış koruyucu; 500+ eşdeğerlik karşılaştırmasıyla doğrulandı).

## [18.0.0] — Önceki sürüm
Qwen 2.5 14B (LM Studio) + MarianMT hibrit motoru, modüler katman mimarisi (core/extractors/translators/renderers), cerrahi redaksiyon render ve üçlü çıktı sistemi.
