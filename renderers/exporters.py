import os
import subprocess
from typing import List, Dict, Optional
import pymupdf as fitz

from core.models import ParagraphBlock
from core.paths import build_path
from core.unicode_sanitizer import format_sub_sup_for_render


# build/layout_out.txt çıktısı Python tarafında hiçbir ParagraphBlock'a
# bağlanmadığı için motorun hesapladığı optimizasyonlar şu an kullanılmıyor.
# Çıktı ileride kutu geometrilerine uygulanacaksa bu bayrak True yapılmalı.
CPP_LAYOUT_ENGINE_ENABLED = False


def find_cpp_engine_path() -> Optional[str]:
    """Platforma göre AiEngine çalıştırılabilirini bulur; yoksa None döner."""
    candidates = ["AiEngine.exe", "AiEngine"] if os.name != "nt" else ["AiEngine.exe"]
    for name in candidates:
        path = build_path(name)
        if os.path.exists(path):
            return path
    return None


def run_cpp_layout_engine(
    all_paragraphs: List[ParagraphBlock],
    font_validator: Optional[fitz.Font]
) -> None:
    if not CPP_LAYOUT_ENGINE_ENABLED:
        print("\n2. [C++ AiEngine] Bu surumde pasif (cikti henuz Python'a baglanmadi); Python Auto-Fit kullanilacak.")
        return

    layout_in = build_path("layout_in.txt")
    layout_out = build_path("layout_out.txt")
    os.makedirs(build_path(), exist_ok=True)  # build dizinini garantile (CWD'den bağımsız)
    if os.path.exists(layout_out):
        try:
            os.remove(layout_out)
        except OSError:
            pass

    with open(layout_in, "w", encoding="utf-8") as f:
        for p in all_paragraphs:
            clean_en = format_sub_sup_for_render(p.text, font_validator).replace("|", " ").replace("\n", " ")
            clean_tr = format_sub_sup_for_render(p.translated_text, font_validator).replace("|", " ").replace("\n", " ")
            f.write(
                f"{p.id}|{p.page_num}|{p.box.x0:.2f}|{p.box.y0:.2f}|"
                f"{p.box.width:.2f}|{p.box.height:.2f}|{p.font_size:.2f}|"
                f"{clean_en}|{clean_tr}\n"
            )

    engine_path = find_cpp_engine_path()
    if engine_path:
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
