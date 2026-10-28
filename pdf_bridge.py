import argparse
import os
import re
import warnings
from typing import List, Dict

# pyproject.toml'daki version alanıyla senkron tutulmalı (sürümlerde).
__version__ = "18.1.0"

# Motor sürüm etiketi: CLI çıktı mesajlarında kullanılır (pyproject ile uyumlu).
ENGINE_VERSION = "18.1.0"

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
    ExtractionCheckpoint,
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


def parse_page_selection(spec: str, total_pages: int) -> List[int]:
    """'1-10', '3', '1,2,5-8' biçimindeki 1 tabanlı seçimi sıralı 0 tabanlı
    sayfa indekslerine çevirir. Aralıklar toplam sayfaya clamp'lenir
    ('1-1000000000' gibi girdiler RAM'i kilitlemesin diye) ve aralık dışı
    kısım uyarıyla düşürülür."""
    selected = set()
    had_out_of_range = False
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                raise ValueError(f"Gecersiz sayfa araligi: {part} (baslangic > bitis)")
            if a < 1 or b > total_pages:
                had_out_of_range = True
            a, b = max(1, a), min(b, total_pages)
            if a <= b:
                selected.update(range(a - 1, b))
        elif part.isdigit():
            n = int(part)
            if 1 <= n <= total_pages:
                selected.add(n - 1)
            else:
                had_out_of_range = True
        else:
            raise ValueError(f"Gecersiz sayfa ifadesi: {part!r}")

    if had_out_of_range:
        print(f"[UYARI] Secimin bir kismi aralik disinda oldugu icin dusturuldu (toplam sayfa: {total_pages}).")

    valid = sorted(selected)
    if not valid:
        raise ValueError(f"Sayfa secimi bos: {spec!r}")
    return valid


def run_analysis(
    input_pdf: str,
    *,
    allow_ocr: bool = True,
    pages: List[int] = None,
    print_fn=print,
) -> Dict:
    """Çeviri başlamadan kitabın kompozisyon raporu (salt-okunur, motor kurulmaz).

    Kaç blok ne kadarı düz metin / kod / formül / üst-alt bilgi ve kaç sayfanın
    OCR'a düştüğü gösterilir; çevrilecek işin büyüklüğü önceden görülür.
    Hafif kurulumda da çalışır (torch/transformers gerekmez).
    """
    from extractors import GeometricLayoutEngine

    layout_engine = GeometricLayoutEngine(allow_ocr=allow_ocr)
    doc = open_input_document(input_pdf)
    try:
        total_pages = len(doc)
        page_list = sorted(set(pages)) if pages is not None else list(range(total_pages))

        stats = {
            "total_pages": total_pages,
            "analyzed_pages": len(page_list),
            "blocks": 0,
            "prose": 0,
            "code": 0,
            "math": 0,
            "header_footer": 0,
            "ocr_blocks": 0,
        }
        per_page = []

        for page_num in page_list:
            paras = layout_engine.extract_paragraphs(doc[page_num], page_num)
            counts = {"prose": 0, "code": 0, "math": 0, "header_footer": 0, "ocr": 0}
            for p in paras:
                stats["blocks"] += 1
                if p.is_code_block:
                    stats["code"] += 1
                    counts["code"] += 1
                elif p.is_header_footer:
                    stats["header_footer"] += 1
                    counts["header_footer"] += 1
                elif p.is_standalone_math:
                    stats["math"] += 1
                    counts["math"] += 1
                else:
                    stats["prose"] += 1
                    counts["prose"] += 1
                if p.is_from_ocr:
                    stats["ocr_blocks"] += 1
                    counts["ocr"] += 1
            per_page.append((page_num, counts))

        def pct(n):
            return f"%{100.0 * n / stats['blocks']:.1f}" if stats["blocks"] else "%0.0"

        print_fn("==================== ON ANALIZ RAPORU ====================")
        print_fn(f"  Belge          : {input_pdf}")
        print_fn(f"  Sayfa          : {stats['analyzed_pages']}/{stats['total_pages']}")
        print_fn(f"  Toplam blok    : {stats['blocks']}")
        print_fn(f"  Duz metin      : {stats['prose']:5}  ({pct(stats['prose'])})  <- cevrilecek")
        print_fn(f"  Kod karantina  : {stats['code']:5}  ({pct(stats['code'])})  <- korunur")
        print_fn(f"  Formul/BNF     : {stats['math']:5}  ({pct(stats['math'])})  <- korunur")
        print_fn(f"  Ust/alt bilgi  : {stats['header_footer']:5}  ({pct(stats['header_footer'])})  <- korunur")
        if stats["ocr_blocks"]:
            print_fn(f"  OCR bloklari   : {stats['ocr_blocks']}  (taranmis sayfa tespit edildi)")
        print_fn("-----------------------------------------------------------")
        for page_num, counts in per_page[:10]:
            print_fn(
                f"  Sayfa {page_num + 1:>3}: metin={counts['prose']} kod={counts['code']} "
                f"formul={counts['math']} ust/alt={counts['header_footer']}"
                + (f" ocr={counts['ocr']}" if counts["ocr"] else "")
            )
        if len(per_page) > 10:
            print_fn(f"  ... ve {len(per_page) - 10} sayfa daha")
        print_fn("===========================================================")
        return stats
    finally:
        doc.close()


class PDFInputError(RuntimeError, ValueError):
    """Bozuk veya şifreli PDF girdisi hatası.

    RuntimeError olarak ele alınır (main() yakalayıp temiz mesaj basar);
    ValueError kalıtımı, hatayı ValueError sanan eski çağrıcıları kırmamak
    için geriye dönük uyumluluk amacı taşır.
    """


def open_input_document(input_pdf: str):
    """Şifreli/bozuk girdilerde net hata verir; başarılıysa açık dokümanı döner."""
    try:
        doc = fitz.open(input_pdf)
    except Exception as exc:
        raise PDFInputError(f"PDF acilamadi veya bozuk: {input_pdf} ({exc})") from exc
    if doc.needs_pass:
        doc.close()
        raise PDFInputError("PDF sifreli/korumali; sifresiz bir kopya ile tekrar deneyin.")
    return doc


def is_full_page_selection(page_list: List[int], total_pages: int) -> bool:
    """Sayfa seçimi belgenin TÜM sayfalarını kapsıyorsa True döner.

    Checkpoint yalnız bu koşulda silinmeli; kısmi (--pages) koşularında
    ara checkpoint korunur ki sonraki tam koşu kaldığı yerden devam etsin.
    """
    return set(page_list) == set(range(total_pages))


def run_pipeline(
    input_pdf: str,
    output_pdf: str,
    *,
    allow_ocr: bool = True,
    progress_cb=None,
    resume: bool = True,
    pages: List[int] = None,
) -> None:
    reporter = ProgressReporter(progress_cb)
    device, dtype = get_safe_device()
    layout_engine = GeometricLayoutEngine(allow_ocr=allow_ocr)
    reporter.emit("stage", stage=1, label="1/4 • Nöral Model Yükleniyor...", percent=8.0)
    translator = UniversalTranslationEngine(device, dtype)

    doc = open_input_document(input_pdf)
    try:
        total_pages = len(doc)
        translator.profile_book_domain(doc)

        all_paragraphs: List[ParagraphBlock] = []
        pages_blocks_map: Dict[int, List[ParagraphBlock]] = {}

        print(f"\n[ISLEM BASLADI] Toplam Sayfa: {total_pages} | Belge: {input_pdf}")

        if pages is None:
            page_list = list(range(total_pages))
        else:
            page_list = sorted(set(pages))
            out_of_range = [n for n in page_list if not (0 <= n < total_pages)]
            if out_of_range:
                raise ValueError(f"Sayfa indeksleri 0..{total_pages - 1} araliginda olmali: {out_of_range}")
            if not page_list:
                raise ValueError("Bos sayfa secimi")
            print(f"[SAYFA SECIMI] {len(page_list)}/{total_pages} sayfa islenecek: {[n + 1 for n in page_list][:20]}{'...' if len(page_list) > 20 else ''}")

        checkpoint = ExtractionCheckpoint.create_or_load(
            input_pdf, allow_ocr=allow_ocr, total_pages=total_pages, resume=resume
        )

        global_id = 0
        for page_num in page_list:
            page = doc[page_num]
            if checkpoint.has_page(page_num):
                paras = checkpoint.get_page(page_num)
            else:
                paras = layout_engine.extract_paragraphs(page, page_num)
                checkpoint.add_page(page_num, paras)
            for p in paras:
                p.id = global_id
                global_id += 1
                all_paragraphs.append(p)
            pages_blocks_map[page_num] = paras

        total_blocks = len(all_paragraphs)
        print(f"-> Tespit Edilen Toplam Butunlesik Blok Sayisi: {total_blocks}")
        reporter.emit("stage", stage=2, label=f"2/4 • Akademik Çeviri ({total_blocks} Blok)...", percent=18.0)

        processed_blocks = 0
        for page_num in page_list:
            paras = pages_blocks_map.get(page_num, [])
            for p in paras:
                p.translated_text = translator.translate_block(p)
                processed_blocks += 1

            reporter.emit("progress", done=processed_blocks, total=total_blocks)
            # Her sayfada önbellek floşu: çökme durumunda en fazla o anki sayfanın
            # çevirisi kaybolur (eskiden 10 sayfaya kadar kayıp olabilirdi).
            translator.save_cache()
            if (page_num + 1) % 10 == 0 or page_num == page_list[-1]:
                print(
                    f"   Ceviri Ilerlemesi: {processed_blocks}/{total_blocks} blok "
                    f"(Sayfa {page_num + 1}/{total_pages}) tamamlandi."
                )
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
    finally:
        # Başarı yolunda doc yukarıdaki finally'de zaten kapanır (PyMuPDF'de
        # kapatılmış doc'u tekrar kapatmak hata verir); istisna yollarında
        # kapanış burada garanti edilir.
        if not doc.is_closed:
            doc.close()

    base_name = os.path.splitext(final_pdf_path)[0]
    clean_txt_file = f"{base_name}.txt"
    review_txt_file = f"{base_name}_INCELEME.txt"
    export_copyable_txt_files(all_paragraphs, clean_txt_file, review_txt_file)

    # Kısmi (--pages) koşu, tam-kitap checkpoint'ini silmemeli: bir sonraki tam
    # koşu analiz edilen sayfalardan devam etsin. Yalnız tüm sayfalar işlendiğinde
    # checkpoint temizlenir.
    covered_whole_document = is_full_page_selection(page_list, total_pages)
    if covered_whole_document:
        checkpoint.discard()
        print("[CHECKPOINT] Islem tamamlandi; ara checkpoint temizlendi.")
    else:
        print("[CHECKPOINT] Kismi sayfa secimi: ara checkpoint korundu (tum sayfalar bitene kadar silinmeyecek).")
    reporter.emit("done", output_pdf=final_pdf_path, clean_txt=clean_txt_file, review_txt=review_txt_file)

    print("\n====================================================================")
    print(f"[BASARILI] Moduler Evrensel Motor (v{ENGINE_VERSION}) Ciktilari Uretildi:")
    print(f"  1. Kusursuz PDF Dosyasi        : {final_pdf_path}")
    print(f"  2. Temiz Turkce TXT Dosyasi    : {clean_txt_file}")
    print(f"  3. Karsilastirmali Inceleme TXT: {review_txt_file}")
    print("====================================================================")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf_bridge",
        description="PDF AI Engine Pro — İngilizce akademik PDF'yi Türkçeye çevirir (tamamen çevrimdışı)."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "input_pdf", nargs="?",
        help="Çevrilecek İngilizce PDF dosyası (--doctor/--eval dışında zorunlu)"
    )
    parser.add_argument(
        "-o", "--output-pdf",
        help="Hedef Türkçe PDF (verilmezse '<girdi>_ULTIMATE.pdf' kullanılır)"
    )
    parser.add_argument(
        "--pages",
        help="Yalnızca bu sayfalar çevrilir (1 tabanlı): örn. 1-10 veya 1,2,5-8. "
             "Duman testi ve büyük kitaplarda kısmi deneme için."
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Taranmış sayfalarda Tesseract OCR'i atla (dijital PDF'lerde hızlandırır)"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Var olan mizanpaj checkpoint'ini yok say ve analizleri sıfırdan yap"
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Ortam tanılama raporu çalıştır (bağımlılıklar, font, LM Studio, önbellek)"
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Çeviri kalitesi değerlendirme setini koştur (LM Studio açıksa canlı LLM de sınanır)"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Çevirmeden önce kompozisyon raporu: düz metin/kod/formül oranları (motor kurulmaz, hızlı)"
    )
    return parser


def main(argv: List[str] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.doctor:
        from core.diagnostics import run_doctor
        return run_doctor()

    if args.eval:
        from translators.eval_harness import run_eval
        live = True  # LM Studio kapalıysa harness otomatik offline'a duser
        passed, total = run_eval(live=live)
        return 0 if passed == total else 1

    if not args.input_pdf:
        print("[HATA] Girdi PDF verilmedi (--doctor veya --eval kullanmiyorsaniz zorunlu).")
        return 1

    if not os.path.exists(args.input_pdf):
        print(f"[HATA] Girdi PDF bulunamadi: {args.input_pdf}")
        return 1

    output = args.output_pdf
    if output is None:
        base = os.path.splitext(args.input_pdf)[0]
        if args.pages:
            suffix = "_p" + args.pages.replace(" ", "")
            output = f"{base}{suffix}_ULTIMATE.pdf"
        else:
            output = f"{base}_ULTIMATE.pdf"

    pages = None
    if args.pages:
        import pymupdf as fitz_probe  # toplam sayfa sayısı seçim doğrulaması için
        with fitz_probe.open(args.input_pdf) as probe_doc:
            total_pages = len(probe_doc)
        try:
            pages = parse_page_selection(args.pages, total_pages)
        except ValueError as exc:
            print(f"[HATA] Gecersiz --pages ifadesi: {exc}")
            return 1

    if args.analyze:
        run_analysis(args.input_pdf, allow_ocr=not args.no_ocr, pages=pages)
        return 0

    try:
        run_pipeline(
            args.input_pdf,
            output,
            allow_ocr=not args.no_ocr,
            resume=not args.fresh,
            pages=pages,
        )
    except RuntimeError as exc:
        # Bozuk/şifreli PDF gibi boru hattı hataları CLI'da traceback yerine
        # tek satır temiz mesaja iner (GUI zaten Exception'ı kendisi yakalar).
        print(f"[HATA] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
