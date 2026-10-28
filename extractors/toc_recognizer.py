import re
from typing import List, Dict, Any
import pymupdf as fitz
from core.models import BoundingBox, ParagraphBlock
from core.unicode_sanitizer import normalize_unicode_text


class SpatialTOCRecognizer:
    """
    Sayfa 9-14 (ve genel 1-25) İçindekiler (TOC) sayfalarında nokta liderlerini (........)
    tam Y-bandı boyunca silinecek alana (box.x0 .. right_bound_x0) dahil eden ve
    başlık ile sayfa numarasını çakışmasız kilitleyen 2B Hiza Motoru.
    """
    LEADER_DOTS_RE = re.compile(r'(?:\.\s*){3,}|_{3,}|-{3,}')
    PURE_DOTS_RE = re.compile(r'^[\.\s_\-]+$')
    PAGE_NUM_RE = re.compile(r'^(?:[ivxlcdmIVXLCDM]+|\d{1,4}(?:[\-\.]\d{1,3})?)$')
    SECTION_PREFIX_RE = re.compile(r'^(?:Chapter\s+\d+|Part\s+[IVX\d]+|Appendix\s+[A-Z]|\d+\.\d+(?:\.\d+)?)\b', re.I)

    @classmethod
    def is_toc_or_index_page(cls, page: fitz.Page, raw_spans: List[Dict[str, Any]], page_num: int = 0) -> bool:
        full_txt = page.get_text("text")
        if re.search(r'\b(?:Table\s+of\s+Contents|Contents\s+in\s+Detail|Contents|İçindekiler)\b', full_txt[:700], re.I):
            return True

        leader_lines = len(cls.LEADER_DOTS_RE.findall(full_txt))
        if leader_lines >= 4:
            return True

        if page_num <= 25 and raw_spans:
            page_w = page.rect.width
            right_aligned_nums = sum(
                1 for s in raw_spans
                if s["bbox"][0] > page_w * 0.58 and cls.PAGE_NUM_RE.match(s["text"].strip())
            )
            section_entries = sum(
                1 for s in raw_spans
                if s["bbox"][0] < page_w * 0.45 and cls.SECTION_PREFIX_RE.match(s["text"].strip())
            )
            if right_aligned_nums >= 5 and section_entries >= 2:
                return True
            if right_aligned_nums >= 8:
                return True

        return False

    @classmethod
    def reconstruct_toc_rows(cls, page_num: int, raw_spans: List[Dict[str, Any]], page_w: float) -> List[ParagraphBlock]:
        valid_spans = [s for s in raw_spans if s.get("text", "").strip()]
        sorted_spans = sorted(valid_spans, key=lambda s: ((s["bbox"][1] + s["bbox"][3]) / 2.0, s["bbox"][0]))
        y_bands: List[List[Dict[str, Any]]] = []

        for sp in sorted_spans:
            yc = (sp["bbox"][1] + sp["bbox"][3]) / 2.0
            sh = max(6.5, sp["bbox"][3] - sp["bbox"][1])
            if y_bands:
                prev_band = y_bands[-1]
                prev_yc = sum((s["bbox"][1] + s["bbox"][3]) / 2.0 for s in prev_band) / len(prev_band)
                prev_sh = max(6.5, max(s["bbox"][3] - s["bbox"][1] for s in prev_band))
                tol = max(4.2, min(sh, prev_sh) * 0.55)
                if abs(yc - prev_yc) <= tol:
                    prev_band.append(sp)
                    continue
            y_bands.append([sp])

        title_max_x1_limit = page_w - 55.0
        pnum_lane_x0 = page_w - 45.0
        pnum_lane_x1 = page_w - 15.0

        raw_rows: List[Dict[str, Any]] = []
        for band in y_bands:
            band.sort(key=lambda s: s["bbox"][0])
            title_spans: List[Dict[str, Any]] = []
            page_num_spans: List[Dict[str, Any]] = []
            band_max_erase_x1 = max(s["bbox"][2] for s in band)

            for idx_s, sp in enumerate(band):
                raw_t = normalize_unicode_text(sp["text"].strip())
                if not raw_t:
                    continue

                is_rightmost = (idx_s == len(band) - 1)
                if cls.PAGE_NUM_RE.match(raw_t) and (
                    sp["bbox"][0] > page_w * 0.50
                    or (is_rightmost and len(band) >= 2 and sp["bbox"][0] > page_w * 0.40)
                ):
                    page_num_spans.append(sp)
                    continue

                if re.match(r'^[\.\s_\-]+$', raw_t):
                    band_max_erase_x1 = max(band_max_erase_x1, sp["bbox"][2])
                    continue

                if cls.LEADER_DOTS_RE.search(raw_t):
                    band_max_erase_x1 = max(band_max_erase_x1, sp["bbox"][2])
                    cleaned_t = cls.LEADER_DOTS_RE.sub(" ", raw_t).strip()
                    m_tail_num = re.search(r'\s+(\d{1,4}|[ivxlcdmIVXLCDM]+)$', cleaned_t)
                    if m_tail_num:
                        num_str = m_tail_num.group(1)
                        cleaned_t = cleaned_t[:m_tail_num.start()].strip()
                        if not page_num_spans:
                            page_num_spans.append({
                                "text": num_str,
                                "bbox": (pnum_lane_x0, sp["bbox"][1], pnum_lane_x1, sp["bbox"][3]),
                                "size": sp.get("size", 9.5),
                                "flags": sp.get("flags", 0),
                                "font": sp.get("font", "")
                            })
                    if cleaned_t:
                        sp_copy = dict(sp)
                        sp_copy["text"] = cleaned_t
                        title_spans.append(sp_copy)
                    continue

                title_spans.append(sp)

            row_y0 = min(s["bbox"][1] for s in band)
            row_y1 = max(s["bbox"][3] for s in band)
            raw_rows.append({
                "title_spans": title_spans,
                "page_num_spans": page_num_spans,
                "band_max_erase_x1": band_max_erase_x1,
                "y0": row_y0,
                "y1": row_y1,
            })

        # Ardışık TOC satırları arasında en az 2.0 pt dikey boşluk bırak
        for i in range(len(raw_rows) - 1):
            next_y0 = raw_rows[i + 1]["y0"]
            if raw_rows[i]["y1"] > next_y0 - 2.0:
                raw_rows[i]["y1"] = max(raw_rows[i]["y0"] + 5.5, next_y0 - 2.0)

        toc_blocks: List[ParagraphBlock] = []
        b_id = 0
        for r_idx, row in enumerate(raw_rows):
            title_spans = row["title_spans"]
            page_num_spans = row["page_num_spans"]
            row_y0 = row["y0"]
            row_y1 = row["y1"]
            next_y0 = raw_rows[r_idx + 1]["y0"] if r_idx + 1 < len(raw_rows) else (row_y1 + 4.0)
            safe_max_y1 = max(row_y0 + 5.5, min(row_y1 + 0.5, next_y0 - 2.0))

            if title_spans:
                title_text = " ".join(normalize_unicode_text(s["text"].strip()) for s in title_spans).strip()
                title_text = cls.LEADER_DOTS_RE.sub(" ", title_text).strip()
                m_tail = re.search(r'[\.\s]+(\d{1,4}|[ivxlcdmIVXLCDM]+)$', title_text)
                if m_tail:
                    if not page_num_spans:
                        page_num_spans.append({
                            "text": m_tail.group(1),
                            "bbox": (pnum_lane_x0, row_y0, pnum_lane_x1, row_y1),
                            "size": title_spans[-1].get("size", 9.5),
                            "flags": 0,
                            "font": ""
                        })
                    title_text = title_text[:m_tail.start()].strip()

                if len(title_text) >= 2 and not cls.PAGE_NUM_RE.match(title_text):
                    x0 = min(s["bbox"][0] for s in title_spans)
                    locked_x1 = min(
                        title_max_x1_limit,
                        max(row["band_max_erase_x1"], max(s["bbox"][2] for s in title_spans))
                    )
                    locked_x1 = max(x0 + 24.0, min(locked_x1, title_max_x1_limit))
                    fs = max(s.get("size", 9.5) for s in title_spans)
                    is_bold = any((s.get("flags", 0) & 16) != 0 or "bold" in s.get("font", "").lower() for s in title_spans)

                    toc_blocks.append(ParagraphBlock(
                        id=b_id,
                        page_num=page_num,
                        box=BoundingBox(x0, row_y0, locked_x1, row_y1),
                        text=title_text,
                        font_size=fs,
                        is_standalone_math=False,
                        is_code_block=False,
                        is_header_footer=False,
                        is_bold=is_bold,
                        max_allowed_x1=title_max_x1_limit,
                        max_allowed_y1=safe_max_y1
                    ))
                    b_id += 1

            if page_num_spans:
                pnum_text = " ".join(s["text"].strip() for s in page_num_spans).strip()
                pfs = max(s.get("size", 9.5) for s in page_num_spans)
                toc_blocks.append(ParagraphBlock(
                    id=b_id,
                    page_num=page_num,
                    box=BoundingBox(pnum_lane_x0, row_y0, pnum_lane_x1, row_y1),
                    text=pnum_text,
                    translated_text=pnum_text,
                    font_size=pfs,
                    is_standalone_math=False,
                    is_code_block=False,
                    is_header_footer=True,
                    is_bold=False,
                    max_allowed_x1=pnum_lane_x1,
                    max_allowed_y1=safe_max_y1
                ))
                b_id += 1

        return toc_blocks
