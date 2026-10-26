import os
import re
import shutil
import py_compile

FILES = {}

# 1. RENDERERS PAKET BAŞLATICI
FILES["renderers/__init__.py"] = r'''from .forensic_auditor import PageForensicAuditor
from .redaction_renderer import RedactionPDFRenderer
from .exporters import export_copyable_txt_files, run_cpp_layout_engine
'''

# 2. OTONOM ÖZ-DEĞERLENDİRME VE ADLİ KALİTE DENETÇİSİ
FILES["renderers/forensic_auditor.py"] = r'''import re
from typing import List, Tuple, Dict
import pymupdf as fitz

from core.models import ParagraphBlock
from core.unicode_sanitizer import DeterministicArtifactPurger


class PageForensicAuditor:
    """
    PDF kaydedilmeden hemen önce metin kaybı (omission), çözülmemiş maske kalıntısı
    ve 2B kutu çakışmalarını (overlap) denetleyip otomatik onaran adli kalite katmanı.
    """
    NUMBER_INVARIANT_RE = re.compile(r'\b(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?)\b')

    @classmethod
    def audit_and_repair_translation(
        cls, orig_text: str, trans_text: str, masks: Dict[str, str]
    ) -> str:
        repaired = DeterministicArtifactPurger.sanitize_stream(trans_text)

        for key, val in masks.items():
            m_type = "CODE" if "CODE" in key else "MTH"
            num = re.sub(r'\D', '', key)
            repaired = re.sub(rf'\b{m_type}[_\-\s]?{num}\b', lambda _, v=val: v, repaired, flags=re.I)

        if len(repaired) < len(orig_text) * 0.28 and len(orig_text) > 35:
            return DeterministicArtifactPurger.sanitize_stream(orig_text)

        for _, val in masks.items():
            clean_val = val.strip()
            if len(clean_val) >= 2 and clean_val not in repaired:
                repaired = f"{repaired} ({clean_val})"

        return DeterministicArtifactPurger.sanitize_stream(repaired)

    @staticmethod
    def enforce_zero_overlap_geometry(
        render_queue: List[Tuple[ParagraphBlock, fitz.Rect, str, Tuple[float, float, float], Tuple[float, float, float]]],
        protected_rects: List[fitz.Rect]
    ) -> None:
        n = len(render_queue)
        for i in range(n):
            _, rect_i, _, _, _ = render_queue[i]
            for prot_r in protected_rects:
                if rect_i.intersects(prot_r):
                    inter = rect_i & prot_r
                    if inter.width > 4.0 and inter.height > 1.5:
                        if prot_r.y0 >= rect_i.y0 and (prot_r.y0 - rect_i.y0) > 6.0:
                            rect_i.y1 = min(rect_i.y1, prot_r.y0 - 0.8)

            for j in range(i + 1, n):
                _, rect_j, _, _, _ = render_queue[j]
                if rect_i.intersects(rect_j):
                    inter = rect_i & rect_j
                    if inter.width > 6.0 and inter.height > 1.0:
                        if rect_i.y0 <= rect_j.y0 and (rect_j.y0 - rect_i.y0) > 6.0:
                            rect_i.y1 = min(rect_i.y1, rect_j.y0 - 0.5)
'''

# 3. GERÇEK PYMUPDF REDACTION VE DİNAMİK TİPOGRAFİ RENDER MOTORU
FILES["renderers/redaction_renderer.py"] = r'''import os
from typing import List, Tuple, Dict, Optional
import numpy as np
import pymupdf as fitz

from core.models import BoundingBox, ParagraphBlock
from core.hardware import release_memory
from core.unicode_sanitizer import format_sub_sup_for_render
from renderers.forensic_auditor import PageForensicAuditor


class RedactionPDFRenderer:
    """
    Gerçek PyMuPDF Redaction API (add_redact_annot + apply_redactions) kullanarak
    ghosting (çift katman) sorununu sıfırlayan ve iki sütunlu mizanpajı koruyan motor.
    """
    def __init__(self, font_reg_path: str, font_bold_path: str, font_validator: Optional[fitz.Font]):
        self.font_reg_path = font_reg_path
        self.font_bold_path = font_bold_path
        self.font_validator = font_validator

    @staticmethod
    def _sample_background_color(page_pix: fitz.Pixmap, box: BoundingBox) -> Tuple[float, float, float]:
        try:
            w, h = page_pix.width, page_pix.height
            mx, my = int((box.x0 + box.x1) / 2.0), int((box.y0 + box.y1) / 2.0)
            coords = [
                (int(box.x0) - 4, my),
                (int(box.x1) + 4, my),
                (mx, int(box.y0) - 4),
                (mx, int(box.y1) - 4),
                (int(box.x0) - 3, int(box.y0) - 3),
                (int(box.x1) + 3, int(box.y0) - 3),
            ]
            pxs = [list(page_pix.pixel(max(0, min(w - 1, sx)), max(0, min(h - 1, sy)))[:3]) for sx, sy in coords]
            med = np.median(np.array(pxs, dtype=np.float32), axis=0)
            return (float(med[0]) / 255.0, float(med[1]) / 255.0, float(med[2]) / 255.0)
        except Exception:
            return (1.0, 1.0, 1.0)

    @staticmethod
    def _clip_erase_rect_against_obstacle(rect_erase: fitz.Rect, obs_rect: fitz.Rect) -> fitz.Rect:
        if not rect_erase.intersects(obs_rect):
            return rect_erase

        clipped = fitz.Rect(rect_erase)
        if obs_rect.y0 >= clipped.y0 and obs_rect.y0 < clipped.y1 and obs_rect.y0 > clipped.y0 + 2.0:
            clipped.y1 = obs_rect.y0 - 0.5
        elif obs_rect.y1 > clipped.y0 and obs_rect.y1 <= clipped.y1 and obs_rect.y1 < clipped.y1 - 2.0:
            clipped.y0 = obs_rect.y1 + 0.5
        elif obs_rect.x0 >= clipped.x0 and obs_rect.x0 < clipped.x1 and obs_rect.x0 > clipped.x0 + 4.0:
            clipped.x1 = obs_rect.x0 - 0.5
        elif obs_rect.x1 > clipped.x0 and obs_rect.x1 <= clipped.x1 and obs_rect.x1 < clipped.x1 - 4.0:
            clipped.x0 = obs_rect.x1 + 0.5
        return clipped

    @staticmethod
    def _find_optimal_fontsize_and_leading(
        scratch_page: fitz.Page,
        target_rect: fitz.Rect,
        text: str,
        fontname: str,
        original_fontsize: float,
        align: int
    ) -> Tuple[float, float]:
        start_fs = min(18.0, max(6.0, original_fontsize * 0.92))
        fs = start_fs
        while fs >= 6.0:
            for lh in (1.15, 1.08, 1.00, 0.94, 0.88):
                shape = scratch_page.new_shape()
                rc = shape.insert_textbox(
                    target_rect,
                    text,
                    fontsize=fs,
                    fontname=fontname,
                    align=align,
                    lineheight=lh
                )
                if rc >= 0:
                    return fs, lh
            fs -= 0.35
        return 6.0, 0.88

    def render_document(
        self,
        doc: fitz.Document,
        pages_blocks_map: Dict[int, List[ParagraphBlock]],
        device
    ) -> None:
        total_pages = len(doc)
        scratch_doc = fitz.open()
        scratch_page = scratch_doc.new_page(width=800, height=1200)
        if os.path.exists(self.font_reg_path):
            scratch_page.insert_font(fontname="math_tr", fontfile=self.font_reg_path)
            scratch_page.insert_font(fontname="math_tr_b", fontfile=self.font_bold_path)

        for page_num in range(total_pages):
            page = doc[page_num]
            page_paras = pages_blocks_map.get(page_num, [])
            if not page_paras:
                continue

            page_pix = page.get_pixmap()
            page_dict = page.get_text("dict")
            image_rects = [
                fitz.Rect(b["bbox"]) for b in page_dict.get("blocks", [])
                if b.get("type") == 1 and "bbox" in b
            ]
            protected_rects = [
                fitz.Rect(p.box.x0, p.box.y0, p.box.x1, p.box.y1)
                for p in page_paras if p.is_protected
            ] + [ir for ir in image_rects if ir.width > 30.0 and ir.height > 20.0]

            render_queue: List[Tuple[ParagraphBlock, fitz.Rect, str, Tuple[float, float, float], Tuple[float, float, float]]] = []
            has_redactions = False

            for p in page_paras:
                if p.is_protected:
                    continue

                render_text = format_sub_sup_for_render(p.translated_text, self.font_validator)
                if not render_text.strip():
                    continue

                bg_color = p.bg_color if p.bg_color is not None else self._sample_background_color(page_pix, p.box)
                bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
                fg_color = (1.0, 1.0, 1.0) if bg_lum < 0.45 else p.text_color
                if bg_lum >= 0.45 and sum(fg_color) > 2.2:
                    fg_color = (0.0, 0.0, 0.0)

                rect_erase = fitz.Rect(
                    p.box.x0 - 0.5,
                    p.box.y0 - 1.0,
                    p.box.x1 + 3.5,
                    p.box.y1 + 1.0
                )

                for obs_r in protected_rects:
                    rect_erase = self._clip_erase_rect_against_obstacle(rect_erase, obs_r)

                page.add_redact_annot(rect_erase, fill=bg_color)
                has_redactions = True

                safe_x1 = min(p.box.x1, p.max_allowed_x1) if p.max_allowed_x1 else p.box.x1
                safe_x1 = max(safe_x1, p.box.x0 + 16.0)
                desired_y1 = p.box.y1 + 6.0
                safe_y1 = min(desired_y1, p.max_allowed_y1) if p.max_allowed_y1 else desired_y1
                safe_y1 = max(safe_y1, p.box.y1 + 1.5)

                target_rect = fitz.Rect(p.box.x0, p.box.y0 - 1.0, safe_x1, safe_y1)
                render_queue.append((p, target_rect, render_text, fg_color, bg_color))

            if has_redactions:
                try:
                    page.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_NONE,
                        graphics=fitz.PDF_REDACT_LINE_ART_NONE
                    )
                except TypeError:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            PageForensicAuditor.enforce_zero_overlap_geometry(render_queue, protected_rects)

            font_registered = False
            if os.path.exists(self.font_reg_path):
                try:
                    page.insert_font(fontname="math_tr", fontfile=self.font_reg_path)
                    page.insert_font(fontname="math_tr_b", fontfile=self.font_bold_path)
                    font_registered = True
                except Exception:
                    font_registered = False

            for p, target_rect, render_text, fg_color, _ in render_queue:
                used_font = ("math_tr_b" if p.is_bold else "math_tr") if font_registered else "helv"
                align_mode = 1 if p.is_centered else 0

                opt_fs, opt_lh = self._find_optimal_fontsize_and_leading(
                    scratch_page, target_rect, render_text, used_font, p.font_size, align_mode
                )

                rc = page.insert_textbox(
                    target_rect,
                    render_text,
                    fontsize=opt_fs,
                    fontname=used_font,
                    color=fg_color,
                    align=align_mode,
                    lineheight=opt_lh,
                    render_mode=0
                )
                if rc < 0:
                    fallback_y1 = min(
                        (p.max_allowed_y1 + 4.0) if p.max_allowed_y1 else (target_rect.y1 + 12.0),
                        page.rect.height - 6.0
                    )
                    fallback_rect = fitz.Rect(
                        target_rect.x0,
                        target_rect.y0,
                        target_rect.x1,
                        max(target_rect.y1 + 2.0, fallback_y1)
                    )
                    page.insert_textbox(
                        fallback_rect,
                        render_text,
                        fontsize=6.0,
                        fontname=used_font,
                        color=fg_color,
                        align=align_mode,
                        lineheight=0.88,
                        render_mode=0
                    )

            if (page_num + 1) % 10 == 0:
                release_memory(device)

        scratch_doc.close()
'''

# 4. TXT VE C++ AIENGINE DIŞA AKTARIM MODÜLÜ
FILES["renderers/exporters.py"] = r'''import os
import subprocess
from typing import List, Dict, Optional
import pymupdf as fitz

from core.models import ParagraphBlock
from core.unicode_sanitizer import format_sub_sup_for_render


def run_cpp_layout_engine(
    all_paragraphs: List[ParagraphBlock],
    font_validator: Optional[fitz.Font]
) -> None:
    layout_in = os.path.join("build", "layout_in.txt")
    layout_out = os.path.join("build", "layout_out.txt")
    os.makedirs("build", exist_ok=True)
    if os.path.exists(layout_out):
        try:
            os.remove(layout_out)
        except OSError:
            _ = None

    with open(layout_in, "w", encoding="utf-8") as f:
        for p in all_paragraphs:
            clean_en = format_sub_sup_for_render(p.text, font_validator).replace("|", " ").replace("\n", " ")
            clean_tr = format_sub_sup_for_render(p.translated_text, font_validator).replace("|", " ").replace("\n", " ")
            f.write(
                f"{p.id}|{p.page_num}|{p.box.x0:.2f}|{p.box.y0:.2f}|"
                f"{p.box.width:.2f}|{p.box.height:.2f}|{p.font_size:.2f}|"
                f"{clean_en}|{clean_tr}\n"
            )

    engine_path = os.path.join("build", "AiEngine.exe")
    if os.path.exists(engine_path):
        print("\n2. [C++ AiEngine] OpenMP ile paralel kutu/font optimizasyonu yapiliyor...")
        subprocess.run([engine_path, layout_in, layout_out], check=False)


def export_copyable_txt_files(
    all_paragraphs: List[ParagraphBlock],
    clean_txt_path: str,
    bilingual_txt_path: str
) -> None:
    pages_map: Dict[int, List[ParagraphBlock]] = {}
    for p in all_paragraphs:
        pages_map.setdefault(p.page_num, []).append(p)

    with open(clean_txt_path, "w", encoding="utf-8") as f_clean:
        f_clean.write("====================================================================\n")
        f_clean.write("   PDF AI ENGINE - TAMAMEN KOPYALANABILIR TURKCE METIN VE KODLAR\n")
        f_clean.write("====================================================================\n\n")
        for page_num in sorted(pages_map.keys()):
            f_clean.write(f"--- [SAYFA {page_num + 1}] ---\n\n")
            for b in sorted(pages_map[page_num], key=lambda x: (round(x.box.y0 / 6), x.box.x0)):
                f_clean.write(f"{format_sub_sup_for_render(b.translated_text, None)}\n\n")

    with open(bilingual_txt_path, "w", encoding="utf-8") as f_bi:
        f_bi.write("====================================================================\n")
        f_bi.write("   PDF AI ENGINE - KARSILASTIRMALI INCELEME VE HATA AYIKLAMA DOSYASI\n")
        f_bi.write("====================================================================\n\n")
        for page_num in sorted(pages_map.keys()):
            f_bi.write(f"==================== SAYFA {page_num + 1} ====================\n\n")
            for b in sorted(pages_map[page_num], key=lambda x: (round(x.box.y0 / 6), x.box.x0)):
                if b.is_code_block:
                    tag = "[KARANTINA KOD BLOGU]"
                elif b.is_header_footer:
                    tag = "[KORUNAN UST/ALT BILGI]"
                elif b.is_standalone_math:
                    tag = "[KORUNAN FORMUL / BNF]"
                else:
                    tag = f"[METIN BLOGU #{b.id}]"
                orig_out = format_sub_sup_for_render(b.text, None)
                tr_out = format_sub_sup_for_render(b.translated_text, None)
                f_bi.write(f"{tag}\nEN (Orijinal) : {orig_out}\nTR (Ceviri)   : {tr_out}\n" + "-" * 68 + "\n")
            f_bi.write("\n")
'''

# 5. YENİ MODÜLER PDF_BRIDGE.PY (FACADE ORKESTRATÖRÜ)
FILES["pdf_bridge.py"] = r'''import os
import warnings
from typing import List, Dict

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_TOKEN"] = ""
os.environ["HUGGING_FACE_HUB_TOKEN"] = ""

import pymupdf as fitz
warnings.filterwarnings("ignore")
import transformers
transformers.logging.set_verbosity_error()

from core import (
    BoundingBox,
    ParagraphBlock,
    HAS_TESSERACT,
    configure_tesseract,
    get_safe_device,
    release_memory,
    SUPERSCRIPT_MAP,
    SUBSCRIPT_MAP,
    GLYPH_FALLBACK_MAP,
    DeterministicArtifactPurger,
    normalize_unicode_text,
    format_sub_sup_for_render,
    select_best_unicode_fonts,
)
from extractors import (
    FormalismAnalyzer,
    UniversalFormalismQuarantine,
    SpatialTOCRecognizer,
    GeometricLayoutEngine,
)
from translators import (
    CACHE_VERSION,
    SelfHealingCache,
    DynamicAcademicRegistry,
    LMStudioBackend,
    UniversalTranslationEngine,
)
from renderers import (
    PageForensicAuditor,
    RedactionPDFRenderer,
    export_copyable_txt_files,
    run_cpp_layout_engine,
)


def run_pipeline(input_pdf: str, output_pdf: str) -> None:
    device, dtype = get_safe_device()
    layout_engine = GeometricLayoutEngine()
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

    processed_blocks = 0
    for page_num in range(total_pages):
        paras = pages_blocks_map.get(page_num, [])
        for p in paras:
            p.translated_text = translator.translate_block(p)
            processed_blocks += 1

        if (page_num + 1) % 10 == 0 or (page_num + 1) == total_pages:
            print(
                f"   Ceviri Ilerlemesi: {processed_blocks}/{total_blocks} blok "
                f"(Sayfa {page_num + 1}/{total_pages}) tamamlandi."
            )
            translator.save_cache()
            release_memory(device)

    font_reg_path, font_bold_path, font_validator = select_best_unicode_fonts()
    print(f"-> Aktif Font ve Turkce Glif Kalkani: {os.path.basename(font_reg_path)}")

    run_cpp_layout_engine(all_paragraphs, font_validator)

    print("\n3. [CERRAHI RENDER] Gercek Redaction API ve Kod Karantinasi ile PDF isleniyor...")
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

    print("\n====================================================================")
    print("[BASARILI] Moduler Evrensel Motor (v18.0) Ciktilari Uretildi:")
    print(f"  1. Kusursuz PDF Dosyasi        : {final_pdf_path}")
    print(f"  2. Temiz Turkce TXT Dosyasi    : {clean_txt_file}")
    print(f"  3. Karsilastirmali Inceleme TXT: {review_txt_file}")
    print("====================================================================")


if __name__ == "__main__":
    run_pipeline("ornek_belge.pdf", "cevirilmis_belge_ULTIMATE.pdf")
'''

# 6. REQUIREMENTS.TXT VE BASLAT.BAT
FILES["requirements.txt"] = r'''pymupdf>=1.24.0
torch>=2.2.0
transformers>=4.40.0
sentencepiece>=0.2.0
opencv-python>=4.9.0
pillow>=10.0.0
pytesseract>=0.3.10
numpy>=1.26.0
'''

FILES["Baslat.bat"] = r'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [SISTEM] PDF AI Engine (Moduler v18.0) Baslatiliyor...

if exist "C:\Users\efe\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
    "C:\Users\efe\AppData\Local\Python\pythoncore-3.14-64\python.exe" app_gui.py
) else if exist "ai_env\Scripts\python.exe" (
    "ai_env\Scripts\python.exe" app_gui.py
) else (
    python app_gui.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [HATA] Uygulama beklenmedik bir hatayla kapandi.
    pause
)
'''


def patch_app_gui_lambda_scope() -> None:
    gui_path = "app_gui.py"
    if not os.path.exists(gui_path):
        return
    try:
        with open(gui_path, "r", encoding="utf-8") as f:
            code = f.read()
        patched = re.sub(
            r'lambda\s*:\s*messagebox\.showerror\(([^,]+),\s*str\(e\)\)',
            r'lambda err_msg=str(e): messagebox.showerror(\1, err_msg)',
            code
        )
        if patched != code:
            with open(gui_path, "w", encoding="utf-8") as f:
                f.write(patched)
            print("  [ONARILDI] app_gui.py icindeki 'free variable e' Tkinter hatasi giderildi.")
    except Exception as exc:
        print(f"  [UYARI] app_gui.py kontrol edilemedi: {exc}")


def main():
    os.makedirs("renderers", exist_ok=True)
    os.makedirs("build", exist_ok=True)

    if os.path.exists("pdf_bridge.py") and os.path.getsize("pdf_bridge.py") > 15000:
        backup_path = os.path.join("build", "pdf_bridge_monolithic_backup.py")
        shutil.copy2("pdf_bridge.py", backup_path)
        print(f"  [YEDEK] Eski 1700 satirlik pdf_bridge.py -> {backup_path} olarak yedeklendi.")

    for rel_path, content in FILES.items():
        with open(rel_path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
        if rel_path.endswith(".py"):
            py_compile.compile(rel_path, doraise=True)
        print(f"  [OK] Olusturuldu ve dogrulandi: {rel_path}")

    patch_app_gui_lambda_scope()

    print("\n========================================================")
    print("[TUM ADIMLAR TAMAMLANDI!] Moduler Mimari (v18.0) Hazir!")
    print("Artik arayuzu baslatmak icin klasordeki 'Baslat.bat' dosyasina")
    print("cift tiklayabilir veya CMD'de su komutu calistirabilirsin:")
    print(r"C:\Users\efe\AppData\Local\Python\pythoncore-3.14-64\python.exe app_gui.py")
    print("========================================================")


if __name__ == "__main__":
    main()