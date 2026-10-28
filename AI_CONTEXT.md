# PDF AI Book Translator - Mimari Bağlam (AI Context)

Bu depo, akademik ve teknik PDF kitaplarını (Siber Güvenlik, Sayısal Tasarım, Programlama Dilleri vb.) %100 çevrimdışı (air-gapped) ve mizanpajı bozmadan Türkçeye çeviren modüler bir sistemdir. Sürüm: v18.1 (CHANGELOG.md'ye bakınız).

## Yeni AI Oturumları İçin Doğrulama Reçeteleri (bu depoda çalışırken)
Bu makinede torch/transformers/opencv KURULU DEĞİLDİR (GUI/LLM koşusu yapılamaz); saf mantık tam test edilir:
```bash
# 1) Test venv'i (yoksa): python3 -m venv /tmp/pdfai_testenv
#    /tmp/pdfai_testenv/bin/pip install pymupdf numpy pillow pytesseract pytest ruff
/tmp/pdfai_testenv/bin/python -m pytest          # 106 test, ~1 sn (torch/cv2 stub'lanır)
/tmp/pdfai_testenv/bin/python -m ruff check .    # E9+F (sözdizimi+pyflakes)
python3 -m py_compile <değişen dosyalar>         # hızlı derleme kontrolü
# Hafif kurulum kontrolü (torch'suz ortamda paket import edilebilir mi):
/tmp/pdfai_testenv/bin/pdfai-translate --doctor  # 0 hata beklenir (uyarılar normal)
/tmp/pdfai_testenv/bin/pdfai-translate --eval    # offline 12/12 geçmeli
```
Dikkat: pytest'i boru ile koşarken `set -o pipefail` kullanın; commit öncesi her zaman tam paketi koşun. AI davranışı (LLM çevirisi) sadece ortak 16GB VRAM makinede sınanabilir.

## Ortak Makine Doğrulama Listesi (16 GB VRAM)
1. `pdfai-translate --doctor` çıktısını paylaş (bağımlılık+LM Studio raporu).
2. `pdfai-translate kitap.pdf --analyze` kompozisyon raporu (çeviri öncesi, motor kurulmaz).
3. `pdfai-translate --eval` skoru (LM Studio açık; 12/12 hedef).
4. VHDL + siber güvenlik PDF'i ile `--pages 1-5` kısmi tur: kod blokları çevrilmiyor mu, terminal/VHDL satırları karantinada mı (f45af63 düzeltmeleri).
5. GUI "⚙️ Çeviri Ayarları" sekmesi görsel kontrol + tam kitap turu.
6. Uzun kitapta işi ortada kesip yeniden başlat → checkpoint resume mesajı.

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
- CI: `.github/workflows/tests.yml` push/PR'da editable kurulum + `pytest` + `ruff check .` çalıştırır (torch/cv2'siz, conftest stub'ları sayesinde hızlı).
- Lint: `ruff.toml` yalnızca E9+F (sözdizimi + pyflakes); stil kuralları kapalıdır.
- Paketleme: `pyproject.toml` (pdf-ai-translator 18.0.0; `pip install -e .`, konsol komutu `pdfai-translate` → `pdf_bridge.main()`). Ağır AI stack'i bilinçli olarak `[ai]` extra'sında: sihirbaz CUDA torch'u PyTorch indeksten kurar, sert bağımlılık olsaydı çakışırdı. `requirements.txt` sürümleri sınırlı aralıklarla bağlıdır.

## Yapılandırma ve İlerleme Kanalı
- `run_pipeline(input_pdf, output_pdf, *, allow_ocr=True, progress_cb=None, resume=True)`; `progress_cb(event, detail)` olayları: `"stage"` ({stage, label, percent}), `"progress"` ({done, total}), `"done"` ({output_pdf, clean_txt, review_txt}).
- LM Studio ortam değişkenleri: `PDF_AI_LMSTUDIO_URL`, `PDF_AI_LMSTUDIO_PORT`, `PDF_AI_LMSTUDIO_MODEL`, `PDF_AI_LMSTUDIO_TIMEOUT`, `PDF_AI_LMSTUDIO_CHECK_TIMEOUT`, `PDF_AI_LMSTUDIO_ATTEMPTS`; font: `PDF_AI_FONT_REGULAR` / `PDF_AI_FONT_BOLD`.

## Checkpoint / Resume
- `core/checkpoint.py`: mizanpaj analizi sayfa sayfa `build/checkpoints/<ad>_<parmakizi>.jsonl`'a yazılır (satır bazlı JSON; çökmede yarım son satır yüklenirken yok sayılır).
- Parmak izi = boyut + mtime + ilk 64KB md5; `allow_ocr` bayrağı kimliğe dahildir. Girdi değişirse checkpoint otomatik geçersiz.
- Çeviri devam etme `SelfHealingCache` üzerinden; cache artık her sayfada floşlanır (kompakt JSON). Başarılı iş sonunda checkpoint dosyası silinir.
- CLI: `--fresh` checkpoint'i yok sayar (`resume=False`).

## Tanılama, Değerlendirme, Kısmi Çeviri
- `--doctor` (`core/diagnostics.py`): salt-okunur ortam raporu; hafif kurulumda (torch/cv2 yok) da çalışır — bu nedenle `core/hardware.py`, `translators/marian_backend.py` (torch) ve `extractors/layout_engine.py` (cv2) import'ları guard'lıdır, eksik pakette açık RuntimeError verir.
- `--eval` (`translators/eval_harness.py`): 12 altın vaka; offline mod deterministik zinciri (ön-normalizasyon→maske→onarım→temizlik) sınar, LM Studio açıksa canlı LLM'i de (maske kalıntısı, yasak terim, uzunluk oranı) sınar. Başarısız vaka = çıkış kodu 1.
- `--pages 1-10` (`parse_page_selection`): 1 tabanlı seçim; seçilmeyen sayfalar çıktıda orijinal kalır; varsayılan çıktı adı `<ad>_p1-10_ULTIMATE.pdf` olur. `run_pipeline(..., pages=[0 tabanlı indeksler])`.
- GUI "⚙️ Çeviri Ayarları" sekmesi: LM Studio URL/port/model, OCR, sayfa aralığı, sıfırdan başla — `core/user_settings.py` üzerinden `build/gui_settings.json`'da kalıcı; başlat anında toplanır, env'e uygulanır ve run_pipeline kwarg'larına geçer.
