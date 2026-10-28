# PDF AI Book Translator - Mimari Bağlam (AI Context)

Bu depo, akademik ve teknik PDF kitaplarını (Siber Güvenlik, Sayısal Tasarım, Programlama Dilleri vb.) %100 çevrimdışı (air-gapped) ve mizanpajı bozmadan Türkçeye çeviren modüler bir sistemdir.

## Yapay Zeka Asistanları İçin Kurallar
1. Tüm projeyi tek dosyada birleştirmeyin. Her modül ortalama 100-250 satırdır; yalnızca ilgili modülü düzenleyin.
2. `app_gui.py` doğrudan `pdf_bridge.run_pipeline(input_pdf, output_pdf)` fonksiyonunu çağırır. Bu imzayı asla değiştirmeyin (opsiyonel keyword argümanları eklenebilir).
3. Kod blokları (`is_code_block`), matematik/BNF ifadeleri (`is_standalone_math`) ve üst/alt bilgiler (`is_header_footer`) `p.is_protected == True` döndürür; asla çevrilmez ve asla `redact` edilmez.
4. Değişikliklerden sonra `pytest` çalıştırın; `tests/` ağır AI bağımlılıkları olmadan koşar (eksik torch/cv2 stub'lanır).

## Modül Haritası
- `core/models.py`: `BoundingBox` ve `ParagraphBlock` veri yapıları.
- `core/hardware.py`: NVIDIA GPU (CUDA / Blackwell bfloat16) ve CPU algılama, bellek temizleme (`release_memory`).
- `core/unicode_sanitizer.py`: Saf Hex Unicode tabloları, PUA/Arapça parantez (`\ufd3e`, `\ufd3f`) temizleyici, platform bağımsız Türkçe font seçici (`PDF_AI_FONT_REGULAR/BOLD` ile ezilebilir).
- `extractors/formalism.py`: Monospace/Sözdizimi kod karantinası, 1D-Markov komşuluk yumuşatması (VHDL/Verilog/C/Python) ve 2 aşamalı `⟦CODE_X⟧` maskeleme.
- `extractors/toc_recognizer.py`: İçindekiler (TOC) sayfaları için 2B Y-Band kümeleme ve sağ sayfa numarası kilitleme.
- `extractors/layout_engine.py`: Dijital vektör metin okuma, 2 sütun orta boşluk (gutter) analizi, yetim satır birleştirme ve taranmış sayfa OCR motoru.
- `translators/`: Self-healing önbellek, Dinamik Alan Kayıtçısı, LM Studio (Yerel LLM) ve Helsinki-NLP (Opus-MT) çeviri motorları.
- `renderers/`: Adli kalite denetçisi (`PageForensicAuditor`), gerçek PyMuPDF Redaction API render motoru ve TXT/C++ çıktıları.
- `pdf_bridge.py`: Boru hattı girişi; CLI: `python pdf_bridge.py giris.pdf -o cikti.pdf [--no-ocr]`.
- `tests/`: pytest paketi (sanitizer, formalism, TOC, adli denetçi, önbellek, LM Studio istemcisi).

## Bilinen Durum
- C++ AiEngine (`renderers.CPP_LAYOUT_ENGINE_ENABLED=False`) varsayılan pasif: `layout_out.txt` çıktısı hiçbir Python koduna bağlanmamıştı; çıktı bağlanana kadar kapalı kalır.
- Linux/macOS desteklenir (`Baslat.sh`); Windows'ta `Kurulum_Yap.bat` + `Baslat.bat` kullanılır.
- CI: `.github/workflows/tests.yml` push/PR'da `pytest` + `ruff check .` çalıştırır (torch/cv2'siz, conftest stub'ları sayesinde hızlı).
- Lint: `ruff.toml` yalnızca E9+F (sözdizimi + pyflakes); stil kuralları kapalıdır.

## Yapılandırma ve İlerleme Kanalı
- `run_pipeline(input_pdf, output_pdf, *, allow_ocr=True, progress_cb=None)`; `progress_cb(event, detail)` olayları: `"stage"` ({stage, label, percent}), `"progress"` ({done, total}), `"done"` ({output_pdf, clean_txt, review_txt}).
- LM Studio ortam değişkenleri: `PDF_AI_LMSTUDIO_URL`, `PDF_AI_LMSTUDIO_PORT`, `PDF_AI_LMSTUDIO_MODEL`, `PDF_AI_LMSTUDIO_TIMEOUT`, `PDF_AI_LMSTUDIO_CHECK_TIMEOUT`, `PDF_AI_LMSTUDIO_ATTEMPTS`; font: `PDF_AI_FONT_REGULAR` / `PDF_AI_FONT_BOLD`.
