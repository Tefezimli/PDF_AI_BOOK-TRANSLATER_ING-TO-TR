import argparse
import os
import warnings
from typing import List, Dict

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_TOKEN"] = ""
os.environ["HUGGING_FACE_HUB_TOKEN"] = ""

import pymupdf as fitz
warnings.filterwarnings("ignore")
try:
    import transformers
    transformers.logging.set_verbosity_error()
except ImportError:
    # Hafif kurulumda ([ai] extra'sı yok): --help ve argparse yine çalışsın;
    # çeviri başlarken transformers eksikse motor kendi açık hatasını verir.
    transformers = None

from core import (
    ParagraphBlock,
    get_safe_device,
    release_memory,
    select_best_unicode_fonts,
)
from extractors import GeometricLayoutEngine
from translators import UniversalTranslationEngine
from renderers import (
    RedactionPDFRenderer,
    export_copyable_txt_files,
    run_cpp_layout_engine,
)


class ProgressReporter:
    """run_pipeline için opsiyonel yapılandırılmış ilerleme kanalı.

    GUI'ler ve dış betikler stdout kazıma yerine bu olayları dinleyebilir:
      - ("stage",    {"stage": int, "label": str, "percent": float})
      - ("progress", {"done": int, "total": int})
      - ("done",     {"output_pdf": str, "clean_txt": str, "review_txt": str})
    Geri çağrının kendi hatası boru hattını asla durdurmaz.
    """

    def __init__(self, callback=None):
        self.callback = callback

    def emit(self, event: str, **detail) -> None:
        if self.callback is None:
            return
        try:
            self.callback(event, detail)
        except Exception:
            pass


def run_pipeline(input_pdf: str, output_pdf: str, *, allow_ocr: bool = True, progress_cb=None) -> None:
    reporter = ProgressReporter(progress_cb)
    device, dtype = get_safe_device()
    layout_engine = GeometricLayoutEngine(allow_ocr=allow_ocr)
    reporter.emit("stage", stage=1, label="1/4 • Nöral Model Yükleniyor...", percent=8.0)
    translator = UniversalTranslationEngine(device, dtype)

    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    translator.profile_book_domain(doc)

    all_paragraphs: List[ParagraphBlock] = []
    pages_blocks_map: Dict[int, List[ParagraphBlock]] = {}

    print(f"\n[ISLEM BASLADI] Toplam Sayfa: {total_pages} | Belge: {input_pdf}")

    global_id = 0
    for page_num in range(total_pages):
        page = doc[page_num]
        paras = layout_engine.extract_paragraphs(page, page_num)
        for p in paras:
            p.id = global_id
            global_id += 1
            all_paragraphs.append(p)
        pages_blocks_map[page_num] = paras

    total_blocks = len(all_paragraphs)
    print(f"-> Tespit Edilen Toplam Butunlesik Blok Sayisi: {total_blocks}")
    reporter.emit("stage", stage=2, label=f"2/4 • Akademik Çeviri ({total_blocks} Blok)...", percent=18.0)

    processed_blocks = 0
    for page_num in range(total_pages):
        paras = pages_blocks_map.get(page_num, [])
        for p in paras:
            p.translated_text = translator.translate_block(p)
            processed_blocks += 1

        reporter.emit("progress", done=processed_blocks, total=total_blocks)
        if (page_num + 1) % 10 == 0 or (page_num + 1) == total_pages:
            print(
                f"   Ceviri Ilerlemesi: {processed_blocks}/{total_blocks} blok "
                f"(Sayfa {page_num + 1}/{total_pages}) tamamlandi."
            )
            translator.save_cache()
            release_memory(device)

    font_reg_path, font_bold_path, font_validator = select_best_unicode_fonts()
    if font_reg_path:
        print(f"-> Aktif Font ve Turkce Glif Kalkani: {os.path.basename(font_reg_path)}")
    else:
        print("[UYARI] Turkce glifli sistem fontu bulunamadi; dahili 'helv' fontu kullanilacak.")

    run_cpp_layout_engine(all_paragraphs, font_validator)
    reporter.emit("stage", stage=3, label="3/4 • Mizanpaj Optimizasyonu...", percent=85.0)

    print("\n3. [CERRAHI RENDER] Gercek Redaction API ve Kod Karantinasi ile PDF isleniyor...")
    reporter.emit("stage", stage=4, label="4/4 • Cerrahi PDF Render & TXT Üretimi...", percent=92.0)
    renderer = RedactionPDFRenderer(font_reg_path, font_bold_path, font_validator)
    renderer.render_document(doc, pages_blocks_map, device)

    final_pdf_path = output_pdf
    try:
        doc.save(final_pdf_path, garbage=4, deflate=True)
    except PermissionError:
        base, ext = os.path.splitext(output_pdf)
        final_pdf_path = f"{base}_YENI{ext}"
        print(f"[UYARI] '{output_pdf}' baska bir programda acik! Cikti '{final_pdf_path}' olarak kaydedildi.")
        doc.save(final_pdf_path, garbage=4, deflate=True)
    finally:
        doc.close()

    base_name = os.path.splitext(final_pdf_path)[0]
    clean_txt_file = f"{base_name}.txt"
    review_txt_file = f"{base_name}_INCELEME.txt"
    export_copyable_txt_files(all_paragraphs, clean_txt_file, review_txt_file)
    reporter.emit("done", output_pdf=final_pdf_path, clean_txt=clean_txt_file, review_txt=review_txt_file)

    print("\n====================================================================")
    print("[BASARILI] Moduler Evrensel Motor (v18.0) Ciktilari Uretildi:")
    print(f"  1. Kusursuz PDF Dosyasi        : {final_pdf_path}")
    print(f"  2. Temiz Turkce TXT Dosyasi    : {clean_txt_file}")
    print(f"  3. Karsilastirmali Inceleme TXT: {review_txt_file}")
    print("====================================================================")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf_bridge",
        description="PDF AI Engine Pro — İngilizce akademik PDF'yi Türkçeye çevirir (tamamen çevrimdışı)."
    )
    parser.add_argument("input_pdf", help="Çevrilecek İngilizce PDF dosyası")
    parser.add_argument(
        "-o", "--output-pdf",
        help="Hedef Türkçe PDF (verilmezse '<girdi>_ULTIMATE.pdf' kullanılır)"
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Taranmış sayfalarda Tesseract OCR'i atla (dijital PDF'lerde hızlandırır)"
    )
    return parser


def main(argv: List[str] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not os.path.exists(args.input_pdf):
        print(f"[HATA] Girdi PDF bulunamadi: {args.input_pdf}")
        return 1

    output = args.output_pdf or f"{os.path.splitext(args.input_pdf)[0]}_ULTIMATE.pdf"
    run_pipeline(args.input_pdf, output, allow_ocr=not args.no_ocr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
