import re
from typing import List, Tuple, Dict, Any, Optional
import pymupdf as fitz
from PIL import Image
import cv2
import numpy as np
import pytesseract

from core.models import BoundingBox, ParagraphBlock
from core.hardware import HAS_TESSERACT
from core.unicode_sanitizer import normalize_unicode_text
from extractors.formalism import FormalismAnalyzer, UniversalFormalismQuarantine
from extractors.toc_recognizer import SpatialTOCRecognizer


class GeometricLayoutEngine:
    def extract_paragraphs(self, page: fitz.Page, page_num: int) -> List[ParagraphBlock]:
        raw_text_blocks = page.get_text("blocks")
        has_selectable_text = any(
            b[6] == 0 and len(str(b[4]).strip()) > 0 for b in raw_text_blocks
        )

        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)
        blocks = page_dict.get("blocks", [])

        raw_spans = [
            s for b in blocks if b.get("type") == 0
            for l in b.get("lines", [])
            for s in l.get("spans", []) if s.get("text", "").strip()
        ]
        if has_selectable_text and SpatialTOCRecognizer.is_toc_or_index_page(page, raw_spans, page_num):
            toc_rows = SpatialTOCRecognizer.reconstruct_toc_rows(page_num, raw_spans, page.rect.width)
            if len(toc_rows) >= 4:
                return toc_rows

        digital_blocks = self._extract_digital(page, page_num, blocks)

        final_blocks = list(digital_blocks)
        if not (has_selectable_text and final_blocks) and HAS_TESSERACT:
            ocr_blocks = self._extract_scanned_ocr(page, page_num, quarantined_blocks=digital_blocks)
            if ocr_blocks:
                print(f"   [TARANMIS SAYFA OCR] Sayfa {page_num + 1}: {len(ocr_blocks)} gorsel blok ayristirildi.")
                final_blocks.extend(ocr_blocks)

        for idx, b in enumerate(final_blocks):
            b.id = idx

        return self._compute_two_column_and_collision_limits(final_blocks, page.rect.width, page.rect.height)

    @staticmethod
    def _detect_two_column_gutter(blocks: List[ParagraphBlock], page_w: float) -> Optional[float]:
        mid_left = page_w * 0.42
        mid_right = page_w * 0.58
        left_col = [
            b for b in blocks
            if not b.is_header_footer and b.box.width < page_w * 0.46 and b.box.x1 <= mid_right
        ]
        right_col = [
            b for b in blocks
            if not b.is_header_footer and b.box.width < page_w * 0.46 and b.box.x0 >= mid_left
        ]
        if len(left_col) >= 2 and len(right_col) >= 2:
            max_left_x1 = max(b.box.x1 for b in left_col)
            min_right_x0 = min(b.box.x0 for b in right_col)
            if min_right_x0 > max_left_x1 + 5.0:
                return (max_left_x1 + min_right_x0) / 2.0
        return None

    def _compute_two_column_and_collision_limits(
        self, blocks: List[ParagraphBlock], page_w: float, page_h: float
    ) -> List[ParagraphBlock]:
        gutter_x = self._detect_two_column_gutter(blocks, page_w)
        sorted_b = sorted(blocks, key=lambda b: (b.box.y0, b.box.x0))

        for i, b in enumerate(sorted_b):
            min_next_y0 = page_h - 8.0
            hard_right_limit = b.box.x1
            if gutter_x is not None and b.box.x1 <= gutter_x + 4.0:
                hard_right_limit = min(hard_right_limit, gutter_x - 2.0)

            for j, other in enumerate(sorted_b):
                if i == j:
                    continue
                vert_overlap = min(b.box.y1, other.box.y1) - max(b.box.y0, other.box.y0)
                if vert_overlap > 2.0 and other.box.x0 >= b.box.x1 - 2.0:
                    hard_right_limit = min(hard_right_limit, other.box.x0 - 2.0)

                horiz_overlap = min(b.box.x1, other.box.x1) - max(b.box.x0, other.box.x0)
                if horiz_overlap > 8.0 and other.box.y0 >= b.box.y1 - 1.5:
                    min_next_y0 = min(min_next_y0, other.box.y0)

            b.max_allowed_x1 = max(b.box.x0 + 16.0, hard_right_limit)
            b.max_allowed_y1 = max(b.box.y1 + 2.0, min_next_y0 - 0.8)

        return blocks

    @staticmethod
    def _int_to_rgb(color_int: int) -> Tuple[float, float, float]:
        return (((color_int >> 16) & 255) / 255.0, ((color_int >> 8) & 255) / 255.0, (color_int & 255) / 255.0)

    @staticmethod
    def _join_hyphenated_or_spaced(prev_text: str, next_text: str) -> str:
        p = prev_text.rstrip()
        n = next_text.lstrip()
        if p.endswith("-") and not p.endswith(" -") and len(n) > 0 and n[0].islower():
            return p[:-1] + n
        return f"{p} {n}"

    def _extract_digital(self, page: fitz.Page, page_num: int, blocks: List[Dict[str, Any]]) -> List[ParagraphBlock]:
        page_h = page.rect.height
        page_w = page.rect.width
        size_counts: Dict[float, int] = {}
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    txt = s.get("text", "").strip()
                    if len(txt) >= 3:
                        sz = round(s.get("size", 9.5), 1)
                        size_counts[sz] = size_counts.get(sz, 0) + len(txt)

        page_body_size = max(size_counts.items(), key=lambda x: x[1])[0] if size_counts else 9.5
        out_blocks: List[ParagraphBlock] = []
        p_idx = 0

        for b in blocks:
            if b.get("type") != 0:
                continue
            raw_lines = b.get("lines", [])
            if not raw_lines:
                continue

            block_left_x0 = min(l["bbox"][0] for l in raw_lines if "bbox" in l)
            block_right_x1 = max(l["bbox"][2] for l in raw_lines if "bbox" in l)
            sorted_raw = sorted(raw_lines, key=lambda l: (round(l["bbox"][1] / 2.5), l["bbox"][0]))
            visual_lines: List[Dict[str, Any]] = []

            for rl in sorted_raw:
                rl_bbox = rl.get("bbox", (0, 0, 0, 0))
                rl_spans = rl.get("spans", [])
                if not rl_spans:
                    continue
                if visual_lines:
                    prev = visual_lines[-1]
                    p_bbox = prev["bbox"]
                    same_row = abs(rl_bbox[1] - p_bbox[1]) < 4.0 or abs(rl_bbox[3] - p_bbox[3]) < 4.0
                    horiz_gap = rl_bbox[0] - p_bbox[2]
                    if same_row and -3.0 <= horiz_gap <= 14.0:
                        prev["spans"].extend(rl_spans)
                        prev["bbox"] = (
                            min(p_bbox[0], rl_bbox[0]), min(p_bbox[1], rl_bbox[1]),
                            max(p_bbox[2], rl_bbox[2]), max(p_bbox[3], rl_bbox[3])
                        )
                        continue
                visual_lines.append({"bbox": rl_bbox, "spans": list(rl_spans)})

            parsed_lines: List[Dict[str, Any]] = []
            for vl in visual_lines:
                spans = vl["spans"]
                normal_spans = [
                    s for s in spans
                    if s.get("text", "").strip() and s.get("size", page_body_size) >= page_body_size * 0.86
                ]
                if not normal_spans:
                    normal_spans = [s for s in spans if s.get("text", "").strip()]
                if not normal_spans:
                    continue

                ref_size = max(s.get("size", page_body_size) for s in normal_spans)
                ref_y = normal_spans[0]["origin"][1]

                total_chars = 0
                mono_chars = 0
                bold_chars = 0
                first_color = (0.0, 0.0, 0.0)

                for idx_s, s in enumerate(spans):
                    stxt = s.get("text", "").strip()
                    if not stxt:
                        continue
                    c_len = len(stxt)
                    total_chars += c_len
                    if FormalismAnalyzer.is_monospace_span(s.get("font", ""), s.get("flags", 0)):
                        mono_chars += c_len
                    if (s.get("flags", 0) & 16) or "bold" in s.get("font", "").lower():
                        bold_chars += c_len
                    if idx_s == 0 and "color" in s:
                        first_color = self._int_to_rgb(s["color"])

                line_is_monospace = (total_chars > 0) and (mono_chars / total_chars >= 0.50)

                line_str = ""
                line_sizes = []

                for s in spans:
                    raw_span = normalize_unicode_text(s.get("text", ""))
                    if not raw_span:
                        continue
                    s_size = s.get("size", ref_size)
                    s_y = s["origin"][1]
                    s_flags = s.get("flags", 0)
                    s_bbox = s.get("bbox", (0, 0, 0, 0))
                    s_height = s_bbox[3] - s_bbox[1]
                    span_is_mono = FormalismAnalyzer.is_monospace_span(s.get("font", ""), s_flags)

                    stripped = raw_span.strip()
                    is_short = 1 <= len(stripped) <= 4
                    is_smaller = (s_size < ref_size * 0.85) or (s_height < ref_size * 0.80)
                    dy = s_y - ref_y

                    if not line_is_monospace and is_short and ((s_flags & 1) or (dy < -ref_size * 0.10) or (is_smaller and dy < -ref_size * 0.04)):
                        line_str += f"<sup:{stripped}>"
                    elif not line_is_monospace and is_short and ((dy > ref_size * 0.08) or (is_smaller and dy >= 0.02)):
                        line_str += f"<sub:{stripped}>"
                    else:
                        if line_str and not line_str.endswith(" ") and not raw_span.startswith(" "):
                            line_str += " "
                        if not line_is_monospace and span_is_mono and len(stripped) >= 1:
                            line_str += f"\u27e6INLCODE:{stripped}\u27e7"
                        else:
                            line_str += raw_span
                        line_sizes.append(s_size)
                        if s_size >= ref_size * 0.88:
                            ref_y = s_y

                clean_line = re.sub(r'\s+', ' ', line_str).strip()
                if not clean_line:
                    continue

                l_bbox = vl["bbox"]
                leading_indent = max(0.0, l_bbox[0] - block_left_x0)
                is_code = False if UniversalFormalismQuarantine.is_natural_prose_or_option_line(clean_line) else (line_is_monospace or FormalismAnalyzer.is_code_line_syntax(clean_line, leading_indent))
                l_box_obj = BoundingBox(l_bbox[0], l_bbox[1], l_bbox[2], l_bbox[3])
                is_hdr_ftr = FormalismAnalyzer.is_header_or_footer(clean_line, l_box_obj, page_h)
                is_formal = is_code or is_hdr_ftr or FormalismAnalyzer.is_formal_expression(clean_line)
                avg_sz = sum(line_sizes) / len(line_sizes) if line_sizes else ref_size

                parsed_lines.append({
                    "text": clean_line,
                    "bbox": l_bbox,
                    "size": avg_sz,
                    "bold": bold_chars > (total_chars * 0.45),
                    "color": first_color,
                    "is_code": is_code,
                    "is_hdr_ftr": is_hdr_ftr,
                    "is_formal": is_formal
                })

            parsed_lines = UniversalFormalismQuarantine.apply_spatial_markov_quarantine(
                parsed_lines, block_left_x0, max(block_right_x1, page_w * 0.85)
            )

            grouped: List[Dict[str, Any]] = []
            curr: Dict[str, Any] = {}

            for pl in parsed_lines:
                if curr and not curr["is_code"] and not curr["is_hdr_ftr"] and not pl["is_code"] and not pl["is_hdr_ftr"]:
                    v_gap = pl["bbox"][1] - curr["bbox"][3]
                    word_cnt = len(pl["text"].split())
                    is_orphan_tail = (
                        word_cnt <= 3
                        and not pl["text"].startswith("\u2022")
                        and not curr["text"].rstrip().endswith((".", "!", "?", ":"))
                        and v_gap <= curr["size"] * 1.30
                        and abs(pl["bbox"][0] - curr["bbox"][0]) <= 38.0
                    )
                    if is_orphan_tail:
                        curr["text"] = self._join_hyphenated_or_spaced(curr["text"], pl["text"])
                        b0, b1 = curr["bbox"], pl["bbox"]
                        curr["bbox"] = (min(b0[0], b1[0]), min(b0[1], b1[1]), max(b0[2], b1[2]), max(b0[3], b1[3]))
                        curr["is_formal"] = False
                        continue

                is_standalone = (
                    pl["is_code"]
                    or pl["is_hdr_ftr"]
                    or pl["is_formal"]
                    or pl["text"].startswith("\u2022")
                )
                if is_standalone:
                    if curr:
                        grouped.append(curr)
                        curr = {}
                    grouped.append(pl.copy())
                else:
                    if not curr:
                        curr = pl.copy()
                    else:
                        v_gap = pl["bbox"][1] - curr["bbox"][3]
                        same_style = (curr["bold"] == pl["bold"]) and (abs(curr["size"] - pl["size"]) < 1.2)
                        if v_gap > curr["size"] * 0.95 or not same_style:
                            grouped.append(curr)
                            curr = pl.copy()
                        else:
                            curr["text"] = self._join_hyphenated_or_spaced(curr["text"], pl["text"])
                            b0, b1 = curr["bbox"], pl["bbox"]
                            curr["bbox"] = (min(b0[0], b1[0]), min(b0[1], b1[1]), max(b0[2], b1[2]), max(b0[3], b1[3]))
            if curr:
                grouped.append(curr)

            for item in grouped:
                txt = item["text"].strip()
                if len(txt) < 2 and not item["is_code"]:
                    continue
                bb = item["bbox"]
                box_obj = BoundingBox(bb[0], bb[1], bb[2], bb[3])
                is_hdr_ftr = item["is_hdr_ftr"] or FormalismAnalyzer.is_header_or_footer(txt, box_obj, page_h)
                is_code = item["is_code"]
                is_math = is_code or is_hdr_ftr or FormalismAnalyzer.is_formal_expression(txt)

                out_blocks.append(ParagraphBlock(
                    id=p_idx,
                    page_num=page_num,
                    box=box_obj,
                    text=txt,
                    font_size=max(6.5, min(18.0, item["size"])),
                    is_standalone_math=is_math,
                    is_code_block=is_code,
                    is_header_footer=is_hdr_ftr,
                    is_from_ocr=False,
                    is_bold=item["bold"],
                    text_color=item["color"]
                ))
                p_idx += 1

        merged_out: List[ParagraphBlock] = []
        for blk in out_blocks:
            if (
                merged_out
                and not blk.is_code_block
                and not blk.is_header_footer
                and not merged_out[-1].is_protected
                and len(blk.text.split()) <= 3
                and not blk.text.startswith("\u2022")
                and not merged_out[-1].text.rstrip().endswith((".", "!", "?", ":"))
            ):
                prev_b = merged_out[-1]
                v_gap = blk.box.y0 - prev_b.box.y1
                if -2.0 <= v_gap <= prev_b.font_size * 1.45 and abs(blk.box.x0 - prev_b.box.x0) <= 38.0:
                    prev_b.text = self._join_hyphenated_or_spaced(prev_b.text, blk.text)
                    prev_b.box = BoundingBox(
                        min(prev_b.box.x0, blk.box.x0), min(prev_b.box.y0, blk.box.y0),
                        max(prev_b.box.x1, blk.box.x1), max(prev_b.box.y1, blk.box.y1)
                    )
                    prev_b.is_standalone_math = False
                    continue
            merged_out.append(blk)

        return merged_out

    @staticmethod
    def _sample_outer_ring(
        bgr_img: np.ndarray, x0: int, y0: int, x1: int, y1: int
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float, float]:
        h_img, w_img = bgr_img.shape[:2]
        pad = 5
        ox0, oy0 = max(0, x0 - pad), max(0, y0 - pad)
        ox1, oy1 = min(w_img, x1 + pad), min(h_img, y1 + pad)

        outer_roi = bgr_img[oy0:oy1, ox0:ox1]
        inner_roi = bgr_img[max(0, y0):min(h_img, y1), max(0, x0):min(w_img, x1)]
        if inner_roi.size == 0 or outer_roi.size == 0:
            return (1.0, 1.0, 1.0), (0.0, 0.0, 0.0), 1.0, 0.0

        strips = [
            outer_roi[0:max(1, y0 - oy0), :, :].reshape(-1, 3),
            outer_roi[max(0, outer_roi.shape[0] - (oy1 - y1)):, :, :].reshape(-1, 3),
            outer_roi[:, 0:max(1, x0 - ox0), :].reshape(-1, 3),
            outer_roi[:, max(0, outer_roi.shape[1] - (ox1 - x1)):, :].reshape(-1, 3),
        ]
        ring_px = np.concatenate([p for p in strips if p.size > 0], axis=0)
        if ring_px.size == 0:
            ring_px = outer_roi.reshape(-1, 3)

        bg_bgr = np.median(ring_px, axis=0)
        bg_rgb = (float(bg_bgr[2]) / 255.0, float(bg_bgr[1]) / 255.0, float(bg_bgr[0]) / 255.0)
        bg_lum = 0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]
        gray_ring = 0.299 * ring_px[:, 2] + 0.587 * ring_px[:, 1] + 0.114 * ring_px[:, 0]
        bg_std = float(np.std(gray_ring))

        gray_inner = cv2.cvtColor(inner_roi, cv2.COLOR_BGR2GRAY)
        if bg_lum < 0.45:
            txt_rgb = (1.0, 1.0, 1.0)
        else:
            dark_mask = gray_inner < np.percentile(gray_inner, 22)
            if np.any(dark_mask):
                fg_bgr = np.median(inner_roi[dark_mask], axis=0)
                txt_rgb = (float(fg_bgr[2]) / 255.0, float(fg_bgr[1]) / 255.0, float(fg_bgr[0]) / 255.0)
            else:
                txt_rgb = (0.0, 0.0, 0.0)

        return bg_rgb, txt_rgb, bg_lum, bg_std

    def _extract_scanned_ocr(
        self,
        page: fitz.Page,
        page_num: int,
        quarantined_blocks: List[ParagraphBlock],
        scale: float = 2.5
    ) -> List[ParagraphBlock]:
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        elif pix.n == 1:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        else:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        quarantined_boxes = [qb.box for qb in quarantined_blocks]
        for qb in quarantined_boxes:
            x0, y0 = int(max(0, qb.x0 * scale - 3)), int(max(0, qb.y0 * scale - 3))
            x1, y1 = int(min(bgr.shape[1], qb.x1 * scale + 3)), int(min(bgr.shape[0], qb.y1 * scale + 3))
            bgr[y0:y1, x0:x1] = (255, 255, 255)

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        page_h = page.rect.height
        page_w = page.rect.width

        data = pytesseract.image_to_data(
            Image.fromarray(gray),
            lang="eng",
            config="--oem 3 --psm 3",
            output_type=pytesseract.Output.DICT
        )

        lines_raw: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = {}
        for i in range(len(data["text"])):
            if int(data["level"][i]) != 5:
                continue
            word = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not word or conf < 48.0:
                continue

            w_box = BoundingBox(
                data["left"][i] / scale, data["top"][i] / scale,
                (data["left"][i] + data["width"][i]) / scale, (data["top"][i] + data["height"][i]) / scale
            )
            if any(w_box.overlaps(eb, margin=2.0) for eb in quarantined_boxes):
                continue

            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines_raw.setdefault(key, []).append({
                "text": word, "conf": conf,
                "left": data["left"][i], "top": data["top"][i],
                "width": data["width"][i], "height": data["height"][i]
            })

        raw_segments: List[Dict[str, Any]] = []
        for _, words in lines_raw.items():
            words_sorted = sorted(words, key=lambda w: w["left"])
            segs: List[List[Dict[str, Any]]] = []
            curr_seg: List[Dict[str, Any]] = []
            for w in words_sorted:
                if curr_seg:
                    prev_r = curr_seg[-1]["left"] + curr_seg[-1]["width"]
                    gap = (w["left"] - prev_r) / scale
                    if gap > 18.0:
                        segs.append(curr_seg)
                        curr_seg = [w]
                        continue
                curr_seg.append(w)
            if curr_seg:
                segs.append(curr_seg)

            for seg in segs:
                line_txt = normalize_unicode_text(" ".join(w["text"] for w in seg))
                if len(line_txt) < 2:
                    continue
                avg_conf = sum(w["conf"] for w in seg) / len(seg)
                x0_px, y0_px = min(w["left"] for w in seg), min(w["top"] for w in seg)
                x1_px, y1_px = max(w["left"] + w["width"] for w in seg), max(w["top"] + w["height"] for w in seg)

                bg_rgb, txt_rgb, bg_lum, bg_std = self._sample_outer_ring(bgr, x0_px, y0_px, x1_px, y1_px)
                if bg_std > 42.0 and avg_conf < 82.0:
                    continue

                b_obj = BoundingBox(x0_px / scale, y0_px / scale, x1_px / scale, y1_px / scale)
                raw_segments.append({
                    "text": line_txt,
                    "box": b_obj,
                    "bg_color": bg_rgb,
                    "text_color": txt_rgb,
                    "bg_lum": bg_lum,
                    "is_multi_col": len(segs) > 1
                })

        raw_segments.sort(key=lambda item: (round(item["box"].y0 / 5.0), item["box"].x0))
        merged_blocks: List[ParagraphBlock] = []

        for item in raw_segments:
            b = item["box"]
            txt = item["text"]
            est_fs = max(7.0, min(18.0, b.height * 0.78))
            is_hdr_ftr = FormalismAnalyzer.is_header_or_footer(txt, b, page_h)
            is_code = FormalismAnalyzer.is_code_line_syntax(txt)
            is_formal = is_hdr_ftr or is_code or FormalismAnalyzer.is_formal_expression(txt)

            merged = False
            if not is_formal and not item["is_multi_col"]:
                for prev in reversed(merged_blocks[-3:]):
                    if prev.is_protected or prev.is_table_or_diagram_cell:
                        continue
                    single_lh = prev.font_size / 0.78
                    v_gap = b.y0 - prev.box.y1
                    left_diff = b.x0 - prev.box.x0
                    if (
                        0.0 <= v_gap <= single_lh * 0.52
                        and -14.0 <= left_diff <= 36.0
                        and abs(est_fs - prev.font_size) <= max(est_fs, prev.font_size) * 0.25
                        and not txt.startswith("\u2022")
                        and not prev.text.endswith((".", "!", "?", ";", ":"))
                    ):
                        ends_conn = bool(re.search(
                            r'\b(?:of|to|for|with|which|a|an|the|in|on|by|from|that|than|as|and|or|are|is|be|into|over|between|already|have|has|can|cannot|will|must)\s*$',
                            prev.text, re.I
                        ))
                        reaches_edge = prev.box.x1 > page_w * 0.60
                        is_short_orphan = len(txt.split()) <= 3
                        if ends_conn or is_short_orphan or (reaches_edge and txt[0].islower()):
                            prev.text = self._join_hyphenated_or_spaced(prev.text, txt)
                            prev.box = BoundingBox(
                                min(prev.box.x0, b.x0),
                                min(prev.box.y0, b.y0),
                                max(prev.box.x1, b.x1),
                                max(prev.box.y1, b.y1)
                            )
                            merged = True
                            break

            if not merged:
                merged_blocks.append(ParagraphBlock(
                    id=len(merged_blocks),
                    page_num=page_num,
                    box=b,
                    text=txt,
                    font_size=est_fs,
                    is_standalone_math=is_formal,
                    is_code_block=is_code,
                    is_header_footer=is_hdr_ftr,
                    is_from_ocr=True,
                    is_bold=(est_fs > 13.5) or (item["bg_lum"] < 0.42),
                    is_table_or_diagram_cell=item["is_multi_col"],
                    text_color=item["text_color"],
                    bg_color=item["bg_color"]
                ))

        return merged_blocks
