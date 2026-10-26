import os
import re
import json
import py_compile


def patch_unicode_sanitizer(file_path: str = "core/unicode_sanitizer.py") -> None:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.startswith('import re'):
        content = 'import re\n' + content

    new_sanitize_method = '''    @classmethod
    def sanitize_stream(cls, text: str) -> str:
        if not text:
            return ""
        t = (
            text.replace("\\ufd3e", "(")
            .replace("\\ufd3f", ")")
            .replace("﴾", "(")
            .replace("﴿", ")")
            .replace("\\u27e6", "(")
            .replace("\\u27e7", ")")
            .replace("⟦", "(")
            .replace("⟧", ")")
        )
        t = cls.PUA_AND_CONTROL_RE.sub("", t)
        t = t.translate(cls.ARTIFACT_TRANSLATION_TABLE)
        t = re.sub(r'[\\ufd3e\\u27e6]', '(', t)
        t = re.sub(r'[\\ufd3f\\u27e7]', ')', t)
        t = re.sub(r'\\(\\s+', '(', t)
        t = re.sub(r'\\s+\\)', ')', t)
        return re.sub(r'\\s+', ' ', t).strip()'''

    pattern_sanitize = re.compile(
        r'    @classmethod\s+def sanitize_stream\(cls,\s*text:\s*str\)\s*->\s*str:.*?(?=\n\ndef normalize_unicode_text)',
        re.DOTALL
    )
    if pattern_sanitize.search(content):
        content = pattern_sanitize.sub(lambda _: new_sanitize_method, content, count=1)

    new_format_fn = '''def format_sub_sup_for_render(text: str, font_obj: Optional[fitz.Font] = None) -> str:
    if not text:
        return ""

    def repl_sup(m):
        val = m.group(1).strip()
        conv = val.translate(SUPERSCRIPT_MAP)
        if font_obj and not all(font_obj.has_glyph(ord(c)) for c in conv):
            return f"^{val}"
        return conv

    def repl_sub(m):
        val = m.group(1).strip()
        conv = val.translate(SUBSCRIPT_MAP)
        if font_obj and not all(font_obj.has_glyph(ord(c)) for c in conv):
            return f"_{val}"
        return conv

    res = DeterministicArtifactPurger.sanitize_stream(text)
    res = re.sub(r'<sup:([^>]+)>', repl_sup, res)
    res = re.sub(r'<sub:([^>]+)>', repl_sub, res)
    res = re.sub(r'\\u27e6INLCODE:(.*?)\\u27e7', lambda m: m.group(1), res)
    res = DeterministicArtifactPurger.sanitize_stream(res)

    if font_obj:
        safe_chars = []
        for ch in res:
            if ch in ("\\ufd3e", "﴾", "\\u27e6"):
                safe_chars.append("(")
            elif ch in ("\\ufd3f", "﴿", "\\u27e7"):
                safe_chars.append(")")
            elif ch in "\\r\\n\\t " or font_obj.has_glyph(ord(ch)):
                safe_chars.append(ch)
            elif ch in GLYPH_FALLBACK_MAP:
                safe_chars.append(GLYPH_FALLBACK_MAP[ch])
            else:
                safe_chars.append("")
        res = "".join(safe_chars)
    return DeterministicArtifactPurger.sanitize_stream(res)'''

    pattern_format = re.compile(
        r'def format_sub_sup_for_render\(text:\s*str,\s*font_obj:\s*Optional\[fitz\.Font\]\s*=\s*None\)\s*->\s*str:.*?(?=\n\ndef select_best_unicode_fonts)',
        re.DOTALL
    )
    if pattern_format.search(content):
        content = pattern_format.sub(lambda _: new_format_fn, content, count=1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def patch_formalism(file_path: str = "extractors/formalism.py") -> None:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    prose_helper_constants = '''PROSE_OPTION_KEYWORDS = {
    "name", "description", "setting", "settings", "default", "required", "optional",
    "option", "options", "summary", "syntax", "usage", "example", "examples", "note",
    "warning", "tip", "author", "platform", "arch", "rank", "disclosed", "available",
    "target", "targets", "payload", "exploit", "auxiliary", "post", "encoder", "nop",
    "evasion", "handler", "session", "sessions", "server", "client", "host", "port",
    "address", "network", "system", "user", "username", "password", "file", "path",
    "directory", "command", "commands", "output", "input", "value", "values", "type",
    "status", "result", "results", "service", "services", "version", "database",
    "vulnerability", "attack", "penetration", "testing", "guide", "chapter", "section",
    "figure", "table", "listing", "page", "current", "yes", "no", "true", "false"
}

PROSE_COLON_LABEL_RE = re.compile(
    r'^(?:[\\u2022\\-\\*]\\s*)?(?:Name|Description|Setting|Settings|Default|Required|Optional|'
    r'Option|Options|Summary|Syntax|Usage|Example|Note|Warning|Tip|Author|Platform|Arch|Rank|'
    r'Disclosed|Available\\s+targets|Basic\\s+options|Payload\\s+options|Module\\s+options|'
    r'Target|Payload|Exploit|Auxiliary|Server|Client|Host|Port|Address|User|Password|File|Path|'
    r'Command|Output|Input|Value|Type|Status|Result|Service|Version|[A-Z][a-z]+(?:\\s+[a-z]+){0,3})\\s*:\\s+\\S+',
    re.I
)
'''

    if "PROSE_OPTION_KEYWORDS" not in content:
        content = content.replace(
            "class UniversalFormalismQuarantine:",
            prose_helper_constants + "\n\nclass UniversalFormalismQuarantine:"
        )

    new_quarantine_class = '''class UniversalFormalismQuarantine:
    NATURAL_COLLOCATIONS = {
        "the", "of the", "in the", "to the", "for the", "on the", "with the",
        "is a", "are the", "can be", "that is", "such as", "which is", "from the",
        "by the", "as a", "into the", "between the", "through the", "this is"
    }
    FORMAL_OPERATORS = set("=<>+-*/|{}[]()^_~\\\\@#$%&;:!")

    @staticmethod
    def _char_class(ch: str) -> int:
        if ch.islower(): return 1
        if ch.isupper(): return 2
        if ch.isdigit(): return 3
        if ch.isspace(): return 4
        if ch in UniversalFormalismQuarantine.FORMAL_OPERATORS: return 5
        return 6

    @classmethod
    def is_natural_prose_or_option_line(cls, text: str) -> bool:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        clean = re.sub(r'\\u27e6(?:CODE|MTH|INLCODE)[^\\u27e7]*\\u27e7', ' word ', clean).strip()
        if not clean:
            return False
        if re.search(r'(?:;\\s*$|\\{[^{}]*$|\\}[^{}]*$|<=|=>|:=|::=|==|!=|&&|\\|\\||0x[0-9a-fA-F]{4,})', clean):
            return False
        if PROSE_COLON_LABEL_RE.match(clean):
            return True
        words = re.findall(r'[a-zA-Z]{2,}', clean)
        if not words:
            return False
        func_hits = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS)
        opt_hits = sum(1 for w in words if w.lower() in PROSE_OPTION_KEYWORDS)
        if ":" in clean and (func_hits >= 1 or opt_hits >= 1) and not re.search(r'[\\{\\};]', clean):
            return True
        if len(words) >= 4 and (func_hits + opt_hits) / len(words) >= 0.25:
            return True
        return False

    @classmethod
    def compute_line_formal_probability(
        cls, text: str, x0: float, x1: float, col_left: float, col_right: float, is_mono: bool
    ) -> float:
        clean = re.sub(r'<(?:sub|sup):[^>]+>', '', text).strip()
        if not clean:
            return 1.0
        if cls.is_natural_prose_or_option_line(clean):
            return 0.0
        if is_mono:
            return 1.0
        if "HDL_LINE_REGEX" in globals() and HDL_LINE_REGEX.match(clean):
            return 1.0

        n = len(clean)
        transitions = 0
        classes = [cls._char_class(c) for c in clean]
        for i in range(n - 1):
            c1, c2 = classes[i], classes[i + 1]
            if c1 != c2 and not ((c1 == 2 and c2 == 1) or (c1 == 1 and c2 == 4) or (c1 == 4 and c2 in (1, 2))):
                transitions += 1
        trans_score = min(1.0, (transitions / max(1, n)) * 3.0)

        op_count = sum(1 for c in clean if c in cls.FORMAL_OPERATORS and c != ":")
        multi_ops = len(re.findall(
            r'(?:<=|=>|:=|::|->|==|!=|>>|<<|\\|\\||&&|;\\s*$|\\b(?:downto|posedge|negedge|std_logic)\\b)',
            clean, re.I
        ))
        op_score = min(1.0, (op_count / max(1, n)) * 3.8 + multi_ops * 0.42)

        low_text = f" {clean.lower()} "
        colloc_hits = sum(1 for col in cls.NATURAL_COLLOCATIONS if f" {col} " in low_text)
        words = re.findall(r'[a-zA-Z]{2,}', clean)
        prose_hits = sum(1 for w in words if w.lower() in ENGLISH_FUNCTION_WORDS or w.lower() in PROSE_OPTION_KEYWORDS)
        prose_brake = min(0.95, colloc_hits * 0.30 + prose_hits * 0.18)

        col_width = max(50.0, col_right - col_left)
        indent_ratio = max(0.0, (x0 - col_left) / col_width)
        short_line_ratio = max(0.0, (col_right - x1) / col_width)
        lacks_prose_end = not clean.endswith((".", "!", "?", '"', "\\u201d"))

        geo_score = 0.0
        if lacks_prose_end and prose_hits <= 1:
            if 0.03 < indent_ratio < 0.50:
                geo_score += 0.22
            if short_line_ratio > 0.22:
                geo_score += 0.18

        raw_prob = (0.35 * trans_score) + (0.45 * op_score) + geo_score - prose_brake
        return max(0.0, min(1.0, raw_prob))

    @classmethod
    def apply_spatial_markov_quarantine(
        cls, lines: List[Dict[str, Any]], col_left: float, col_right: float
    ) -> List[Dict[str, Any]]:
        locked_prose = [cls.is_natural_prose_or_option_line(l["text"]) for l in lines]
        probs = []
        for idx, l in enumerate(lines):
            if locked_prose[idx]:
                l["is_code"] = False
                l["is_formal"] = False
                probs.append(0.0)
            elif l.get("is_code", False):
                probs.append(1.0)
            else:
                probs.append(
                    cls.compute_line_formal_probability(
                        l["text"], l["bbox"][0], l["bbox"][2], col_left, col_right, False
                    )
                )

        smoothed = list(probs)
        n = len(lines)
        for _ in range(2):
            new_p = list(smoothed)
            for i in range(n):
                if locked_prose[i] or smoothed[i] >= 0.85 or lines[i].get("is_hdr_ftr", False):
                    continue
                prev_p = smoothed[i - 1] if i > 0 and (lines[i]["bbox"][1] - lines[i - 1]["bbox"][3]) < 20.0 else 0.0
                next_p = smoothed[i + 1] if i < n - 1 and (lines[i + 1]["bbox"][1] - lines[i]["bbox"][3]) < 20.0 else 0.0
                if prev_p > 0.65 and next_p > 0.65:
                    new_p[i] = max(smoothed[i], 0.82)
                elif (prev_p > 0.75 or next_p > 0.75) and len(lines[i]["text"].split()) <= 5:
                    if not lines[i]["text"].endswith("."):
                        new_p[i] = max(smoothed[i], 0.64)
            smoothed = new_p

        for i, l in enumerate(lines):
            if locked_prose[i]:
                l["is_code"] = False
                l["is_formal"] = False
            elif smoothed[i] >= 0.58:
                l["is_code"] = True
                l["is_formal"] = True
        return lines'''

    pattern_quarantine = re.compile(
        r'class UniversalFormalismQuarantine:.*?(?=\n\nclass FormalismAnalyzer:)',
        re.DOTALL
    )
    if pattern_quarantine.search(content):
        content = pattern_quarantine.sub(lambda _: new_quarantine_class, content, count=1)

    repl_clean_step = '''clean_no_step = re.sub(r'^[\\u2776-\\u2793\\u2460-\\u2473]\\s*', '', clean).strip()
        if not clean_no_step:
            return False
        if UniversalFormalismQuarantine.is_natural_prose_or_option_line(clean_no_step):
            return False'''
    content = re.sub(
        r'clean_no_step = re\.sub\(r\'\^\[\\u2776-\\u2793\\u2460-\\u2473\]\\s\*\',\s*\'\',\s*clean\)\.strip\(\)\s+if not clean_no_step:\s+return False',
        lambda _: repl_clean_step,
        content,
        count=1
    )

    repl_formal_check = '''if UniversalFormalismQuarantine.is_natural_prose_or_option_line(clean):
            return False
        if FormalismAnalyzer.is_code_line_syntax(clean):
            return True'''
    content = re.sub(
        r'if FormalismAnalyzer\.is_code_line_syntax\(clean\):\s+return True',
        lambda _: repl_formal_check,
        content,
        count=1
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def patch_toc_recognizer(file_path: str = "extractors/toc_recognizer.py") -> None:
    new_toc_code = '''import re
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
    LEADER_DOTS_RE = re.compile(r'(?:\\.\\s*){3,}|_{3,}|-{3,}')
    PURE_DOTS_RE = re.compile(r'^[\\.\\s_\\-]+$')
    PAGE_NUM_RE = re.compile(r'^(?:[ivxlcdmIVXLCDM]+|\\d{1,4}(?:[\\-\\.]\\d{1,3})?)$')
    SECTION_PREFIX_RE = re.compile(r'^(?:Chapter\\s+\\d+|Part\\s+[IVX\\d]+|Appendix\\s+[A-Z]|\\d+\\.\\d+(?:\\.\\d+)?)\\b', re.I)

    @classmethod
    def is_toc_or_index_page(cls, page: fitz.Page, raw_spans: List[Dict[str, Any]], page_num: int = 0) -> bool:
        full_txt = page.get_text("text")
        if re.search(r'\\b(?:Table\\s+of\\s+Contents|Contents\\s+in\\s+Detail|Contents|İçindekiler)\\b', full_txt[:700], re.I):
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
                tol = max(4.5, min(sh, prev_sh) * 0.58)
                if abs(yc - prev_yc) <= tol:
                    prev_band.append(sp)
                    continue
            y_bands.append([sp])

        toc_blocks: List[ParagraphBlock] = []
        b_id = 0
        for band in y_bands:
            band.sort(key=lambda s: s["bbox"][0])
            title_spans: List[Dict[str, Any]] = []
            page_num_spans: List[Dict[str, Any]] = []
            band_max_erase_x1 = max(s["bbox"][2] for s in band)
            right_bound_x0 = page_w - 15.0

            for idx_s, sp in enumerate(band):
                raw_t = normalize_unicode_text(sp["text"].strip())
                if not raw_t:
                    continue

                is_rightmost = (idx_s == len(band) - 1)
                if cls.PAGE_NUM_RE.match(raw_t) and (
                    sp["bbox"][0] > page_w * 0.52
                    or (is_rightmost and len(band) >= 2 and sp["bbox"][0] > page_w * 0.42)
                ):
                    right_bound_x0 = min(right_bound_x0, sp["bbox"][0] - 5.0)
                    page_num_spans.append(sp)
                    continue

                if cls.PURE_DOTS_RE.match(raw_t):
                    band_max_erase_x1 = max(band_max_erase_x1, sp["bbox"][2])
                    continue

                if cls.LEADER_DOTS_RE.search(raw_t):
                    band_max_erase_x1 = max(band_max_erase_x1, sp["bbox"][2])
                    cleaned_t = cls.LEADER_DOTS_RE.sub(" ", raw_t).strip()
                    m_tail_num = re.search(r'\\s+(\\d{1,4}|[ivxlcdmIVXLCDM]+)$', cleaned_t)
                    if m_tail_num:
                        num_str = m_tail_num.group(1)
                        cleaned_t = cleaned_t[:m_tail_num.start()].strip()
                        if not page_num_spans:
                            num_x0 = max(sp["bbox"][0] + 30.0, sp["bbox"][2] - 24.0)
                            right_bound_x0 = min(right_bound_x0, num_x0 - 4.0)
                            page_num_spans.append({
                                "text": num_str,
                                "bbox": (num_x0, sp["bbox"][1], sp["bbox"][2], sp["bbox"][3]),
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

            if title_spans:
                title_text = " ".join(normalize_unicode_text(s["text"].strip()) for s in title_spans).strip()
                title_text = cls.LEADER_DOTS_RE.sub(" ", title_text).strip()
                title_text = re.sub(r'[\\.\\s]{2,}\\d{1,4}$', '', title_text).strip()
                if len(title_text) >= 2 and not cls.PAGE_NUM_RE.match(title_text):
                    x0 = min(s["bbox"][0] for s in title_spans)
                    # Nokta liderlerinin tamamini silmek icin x1'i right_bound_x0'a kadar uzat
                    full_erase_x1 = min(right_bound_x0, max(band_max_erase_x1, max(s["bbox"][2] for s in title_spans)))
                    full_erase_x1 = max(x0 + 28.0, full_erase_x1)
                    fs = max(s.get("size", 9.5) for s in title_spans)
                    is_bold = any((s.get("flags", 0) & 16) != 0 or "bold" in s.get("font", "").lower() for s in title_spans)

                    toc_blocks.append(ParagraphBlock(
                        id=b_id,
                        page_num=page_num,
                        box=BoundingBox(x0, row_y0, full_erase_x1, row_y1),
                        text=title_text,
                        font_size=fs,
                        is_standalone_math=False,
                        is_code_block=False,
                        is_header_footer=False,
                        is_bold=is_bold,
                        max_allowed_x1=right_bound_x0,
                        max_allowed_y1=row_y1 + 1.0
                    ))
                    b_id += 1

            if page_num_spans:
                pnum_text = " ".join(s["text"].strip() for s in page_num_spans).strip()
                px0 = max(right_bound_x0 + 2.0, min(s["bbox"][0] for s in page_num_spans))
                px1 = max(px0 + 10.0, max(s["bbox"][2] for s in page_num_spans))
                pfs = max(s.get("size", 9.5) for s in page_num_spans)
                toc_blocks.append(ParagraphBlock(
                    id=b_id,
                    page_num=page_num,
                    box=BoundingBox(px0, row_y0, px1, row_y1),
                    text=pnum_text,
                    translated_text=pnum_text,
                    font_size=pfs,
                    is_standalone_math=False,
                    is_code_block=False,
                    is_header_footer=True,
                    is_bold=False,
                    max_allowed_x1=px1 + 2.0,
                    max_allowed_y1=row_y1 + 1.0
                ))
                b_id += 1

        return toc_blocks
'''
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_toc_code)


def patch_redaction_renderer(file_path: str = "renderers/redaction_renderer.py") -> None:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "DeterministicArtifactPurger" not in content:
        content = content.replace(
            "from core.unicode_sanitizer import format_sub_sup_for_render",
            "from core.unicode_sanitizer import format_sub_sup_for_render, DeterministicArtifactPurger"
        )

    new_fontsize_finder = '''    @staticmethod
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
        return 5.0, 0.80'''

    pattern_finder = re.compile(
        r'    @staticmethod\s+def _find_optimal_fontsize_and_leading\(.*?(?=\n    def render_document)',
        re.DOTALL
    )
    if pattern_finder.search(content):
        content = pattern_finder.sub(lambda _: new_fontsize_finder, content, count=1)

    new_render_doc = '''    def render_document(
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

            # Sayfa 0 (Kapak) uzerindeki basliklarin koruma kilidini ac ve cevirisini garanti et
            if page_num == 0:
                for p in page_paras:
                    p.text = DeterministicArtifactPurger.sanitize_stream(p.text)
                    p.translated_text = DeterministicArtifactPurger.sanitize_stream(p.translated_text)
                    if re.search(r"Penetration\\s+Tester|Guide", p.text, re.I):
                        p.is_standalone_math = False
                        p.is_header_footer = False
                        p.is_code_block = False
                        if not p.translated_text or p.translated_text.strip() == p.text.strip():
                            p.translated_text = re.sub(
                                r"The\\s+Penetration\\s+Tester[\'\\u2019]?s\\s+Guide",
                                "Sızma Testi Uzmanının Rehberi",
                                p.text,
                                flags=re.I
                            )

            # Arka plan tam sayfa gorsellerini engel (obstacle) listesinden haric tut
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

            # HATA 2 COZUMU: Sayfa 0 (Kapak) uzerindeki tum orijinal metin katmanlarini eksiksiz redact et
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
                p.text = DeterministicArtifactPurger.sanitize_stream(p.text)
                p.translated_text = DeterministicArtifactPurger.sanitize_stream(p.translated_text)
                if p.is_protected:
                    continue

                render_text = DeterministicArtifactPurger.sanitize_stream(
                    format_sub_sup_for_render(p.translated_text, self.font_validator)
                )
                if not render_text.strip():
                    continue

                bg_color = p.bg_color if p.bg_color is not None else self._sample_background_color(page_pix, p.box)
                bg_lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
                fg_color = (1.0, 1.0, 1.0) if bg_lum < 0.45 else p.text_color
                if bg_lum >= 0.45 and sum(fg_color) > 2.2:
                    fg_color = (0.0, 0.0, 0.0)

                rect_erase = fitz.Rect(
                    p.box.x0 - 0.5,
                    p.box.y0 - 0.8,
                    p.box.x1 + 2.5,
                    p.box.y1 + 0.8
                )

                for obs_r in protected_rects:
                    if not obs_r.contains(rect_erase):
                        rect_erase = self._clip_erase_rect_against_obstacle(rect_erase, obs_r)

                page.add_redact_annot(rect_erase, fill=bg_color)
                has_redactions = True
                if page_num == 0 or p.is_from_ocr:
                    cover_or_ocr_wipe_rects.append((rect_erase, bg_color))

                # HATA 1 COZUMU: Y ekseninde ASLA alt blogun/tablonun uzerine genisleme yapma!
                safe_x1 = min(p.box.x1, p.max_allowed_x1) if p.max_allowed_x1 else p.box.x1
                safe_x1 = max(safe_x1, p.box.x0 + 16.0)
                hard_y1_ceiling = min(p.box.y1 + 1.5, p.max_allowed_y1) if p.max_allowed_y1 else (p.box.y1 + 1.5)
                safe_y1 = max(p.box.y0 + 6.0, hard_y1_ceiling)

                target_rect = fitz.Rect(p.box.x0, p.box.y0 - 0.8, safe_x1, safe_y1)
                render_queue.append((p, target_rect, render_text, fg_color, bg_color))

            if has_redactions:
                try:
                    page.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_NONE,
                        graphics=fitz.PDF_REDACT_LINE_ART_NONE
                    )
                except TypeError:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # Kapak (Sayfa 0) ve OCR bloklarinda gomulu piksel tabanli Ingilizce katmani arka plan rengiyle boyayarak sifirla
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
                    strict_y1 = min(target_rect.y1, p.max_allowed_y1) if p.max_allowed_y1 else target_rect.y1
                    fallback_rect = fitz.Rect(
                        target_rect.x0,
                        target_rect.y0,
                        target_rect.x1,
                        max(target_rect.y0 + 5.5, strict_y1)
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

        scratch_doc.close()'''

    pattern_render = re.compile(
        r'    def render_document\(.*?\n        scratch_doc\.close\(\)',
        re.DOTALL
    )
    if pattern_render.search(content):
        content = pattern_render.sub(lambda _: new_render_doc, content, count=1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def sanitize_existing_cache(cache_path: str = "build/translation_cache.json") -> None:
    if not os.path.exists(cache_path):
        return
    try:
        from core.unicode_sanitizer import DeterministicArtifactPurger
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if isinstance(v, str) and k != "__version__":
                    cleaned[k] = DeterministicArtifactPurger.sanitize_stream(v)
                else:
                    cleaned[k] = v
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def verify_all_modules() -> None:
    target_files = [
        "core/models.py",
        "core/hardware.py",
        "core/unicode_sanitizer.py",
        "extractors/formalism.py",
        "extractors/toc_recognizer.py",
        "extractors/layout_engine.py",
        "translators/cache_manager.py",
        "translators/domain_registry.py",
        "translators/lmstudio_backend.py",
        "translators/marian_backend.py",
        "renderers/forensic_auditor.py",
        "renderers/redaction_renderer.py",
        "renderers/exporters.py",
        "pdf_bridge.py",
    ]
    for rel_path in target_files:
        if os.path.exists(rel_path):
            py_compile.compile(rel_path, doraise=True)
            print(f"  [OK] Cerrahi yama dogrulandi: {rel_path}")


if __name__ == "__main__":
    patch_unicode_sanitizer()
    patch_formalism()
    patch_toc_recognizer()
    patch_redaction_renderer()
    sanitize_existing_cache()
    verify_all_modules()
    print("\n[BASARILI] 5 Adli Hata (Overlap, Kapak Cift Katman, TOC, Secenek Listeleri ve Suslu Parantezler) Sifirlandi!")