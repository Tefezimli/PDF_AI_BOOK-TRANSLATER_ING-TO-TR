import re
import os
from typing import List, Tuple, Dict, Optional
import numpy as np
import pymupdf as fitz

from core.models import BoundingBox, ParagraphBlock
from core.hardware import release_memory
from core.unicode_sanitizer import (
    DeterministicArtifactPurger,
    format_sub_sup_for_render,
    replace_corrupted_brackets,
)
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
        start_fs = min(18.0, max(5.0, original_fontsize * 0.92))
        fs = start_fs
        while fs >= 5.0:
            for lh in (1.12, 1.05, 0.98, 0.92, 0.86, 0.80):
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
            fs -= 0.30
        return 5.0, 0.80

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
            page_area = max(1.0, page.rect.width * page.rect.height)

            if page_num == 0:
                for p in page_paras:
                    p.text = DeterministicArtifactPurger.sanitize_stream(p.text)
                    p.translated_text = DeterministicArtifactPurger.sanitize_stream(p.translated_text)
                    if re.search(r"Penetration\s+Tester|Guide", p.text, re.I):
                        p.is_standalone_math = False
                        p.is_header_footer = False
                        p.is_code_block = False
                        if not p.translated_text or p.translated_text.strip() == p.text.strip():
                            p.translated_text = re.sub(
                                r"The\s+Penetration\s+Tester['\u2019]?s\s+Guide",
                                "Sızma Testi Uzmanının Rehberi",
                                p.text,
                                flags=re.I
                            )

            image_rects = [
                fitz.Rect(b["bbox"]) for b in page_dict.get("blocks", [])
                if b.get("type") == 1 and "bbox" in b
            ]
            non_bg_image_rects = [
                ir for ir in image_rects
                if 30.0 < ir.width and 20.0 < ir.height and (ir.width * ir.height) < (page_area * 0.35)
            ]
            protected_rects = [
                fitz.Rect(p.box.x0, p.box.y0, p.box.x1, p.box.y1)
                for p in page_paras if p.is_protected
            ] + ([] if page_num == 0 else non_bg_image_rects)

            render_queue: List[Tuple[ParagraphBlock, fitz.Rect, str, Tuple[float, float, float], Tuple[float, float, float]]] = []
            cover_or_ocr_wipe_rects: List[Tuple[fitz.Rect, Tuple[float, float, float]]] = []
            has_redactions = False

            if page_num == 0:
                for b in page_dict.get("blocks", []):
                    if b.get("type") != 0:
                        continue
                    for l in b.get("lines", []):
                        lb = l.get("bbox")
                        if not lb:
                            continue
                        l_rect = fitz.Rect(lb[0] - 1.0, lb[1] - 1.0, lb[2] + 2.0, lb[3] + 1.0)
                        for p in page_paras:
                            if not p.is_protected and l_rect.intersects(fitz.Rect(p.box.x0, p.box.y0, p.box.x1, p.box.y1)):
                                bg_c = p.bg_color if p.bg_color is not None else self._sample_background_color(page_pix, p.box)
                                page.add_redact_annot(l_rect, fill=bg_c)
                                cover_or_ocr_wipe_rects.append((l_rect, bg_c))
                                has_redactions = True
                                break

            for p in page_paras:
                p.text = replace_corrupted_brackets(p.text)
                p.translated_text = replace_corrupted_brackets(p.translated_text)
                if p.is_protected:
                    continue

                render_text = format_sub_sup_for_render(p.translated_text, self.font_validator)
                render_text = replace_corrupted_brackets(render_text)
                if not render_text.strip():
                    continue

                bg_color = p.bg_color if p.bg_color is not None else self._sample_background_color(page_pix, p.box)
                bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
                fg_color = (1.0, 1.0, 1.0) if bg_lum < 0.45 else p.text_color
                if bg_lum >= 0.45 and sum(fg_color) > 2.2:
                    fg_color = (0.0, 0.0, 0.0)

                rect_erase = fitz.Rect(
                    p.box.x0 - 0.5,
                    p.box.y0 - 0.6,
                    p.box.x1 + 2.0,
                    p.box.y1 + 0.6
                )

                for obs_r in protected_rects:
                    if not obs_r.contains(rect_erase):
                        rect_erase = self._clip_erase_rect_against_obstacle(rect_erase, obs_r)

                page.add_redact_annot(rect_erase, fill=bg_color)
                has_redactions = True
                if page_num == 0 or p.is_from_ocr:
                    cover_or_ocr_wipe_rects.append((rect_erase, bg_color))

                safe_x1 = min(p.box.x1, p.max_allowed_x1) if p.max_allowed_x1 else p.box.x1
                safe_x1 = max(safe_x1, p.box.x0 + 16.0)
                hard_y1_ceiling = min(p.box.y1 + 1.0, p.max_allowed_y1 - 2.0) if p.max_allowed_y1 else (p.box.y1 + 1.0)
                safe_y1 = max(p.box.y0 + 5.5, hard_y1_ceiling)

                target_rect = fitz.Rect(p.box.x0, p.box.y0 - 0.5, safe_x1, safe_y1)
                render_queue.append((p, target_rect, render_text, fg_color, bg_color))

            if has_redactions:
                try:
                    page.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_NONE,
                        graphics=fitz.PDF_REDACT_LINE_ART_NONE
                    )
                except TypeError:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            for wipe_r, wipe_bg in cover_or_ocr_wipe_rects:
                page.draw_rect(wipe_r, color=wipe_bg, fill=wipe_bg, overlay=True)

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

                render_text = replace_corrupted_brackets(render_text)

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
                    strict_y1 = min(target_rect.y1, p.max_allowed_y1 - 2.0) if p.max_allowed_y1 else target_rect.y1
                    fallback_rect = fitz.Rect(
                        target_rect.x0,
                        target_rect.y0,
                        target_rect.x1,
                        max(target_rect.y0 + 5.0, strict_y1)
                    )
                    page.insert_textbox(
                        fallback_rect,
                        render_text,
                        fontsize=5.0,
                        fontname=used_font,
                        color=fg_color,
                        align=align_mode,
                        lineheight=0.80,
                        render_mode=0
                    )

            if (page_num + 1) % 10 == 0:
                release_memory(device)

        scratch_doc.close()
