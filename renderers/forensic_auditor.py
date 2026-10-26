import re
from typing import List, Tuple, Dict
import pymupdf as fitz

from core.models import ParagraphBlock
from core.unicode_sanitizer import DeterministicArtifactPurger
from translators.domain_registry import DynamicAcademicRegistry


class PageForensicAuditor:
    """
    PDF kaydedilmeden hemen önce metin kaybı (omission), çözülmemiş maske kalıntısı,
    donanım terminolojisi gafları, ﴾ ﴿ (\ufd3e, \ufd3f) parantezleri ve 2B kutu
    çakışmalarını (overlap) denetleyip otomatik onaran adli kalite katmanı.
    """
    NUMBER_INVARIANT_RE = re.compile(r'\b(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?)\b')

    @classmethod
    def audit_and_repair_translation(
        cls, orig_text: str, trans_text: str, masks: Dict[str, str]
    ) -> str:
        repaired = DynamicAcademicRegistry.apply_post_fixes(trans_text)
        repaired = DeterministicArtifactPurger.sanitize_stream(repaired)

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

        repaired = DynamicAcademicRegistry.apply_post_fixes(repaired)
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
                horiz_ov = min(rect_i.x1, prot_r.x1) - max(rect_i.x0, prot_r.x0)
                if horiz_ov > 2.0 and prot_r.y0 >= rect_i.y0 and (prot_r.y0 - rect_i.y0) > 5.0:
                    if rect_i.y1 > prot_r.y0 - 2.0:
                        rect_i.y1 = min(rect_i.y1, prot_r.y0 - 2.0)
                if rect_i.intersects(prot_r):
                    inter = rect_i & prot_r
                    if inter.height > 1.0 and prot_r.x0 > rect_i.x0 + 18.0:
                        rect_i.x1 = min(rect_i.x1, prot_r.x0 - 2.0)

            for j in range(n):
                if i == j:
                    continue
                _, rect_j, _, _, _ = render_queue[j]
                horiz_ov = min(rect_i.x1, rect_j.x1) - max(rect_i.x0, rect_j.x0)
                if horiz_ov > 4.0 and rect_i.y0 < rect_j.y0:
                    if rect_i.y1 > rect_j.y0 - 2.0 and (rect_j.y0 - rect_i.y0) > 5.0:
                        rect_i.y1 = min(rect_i.y1, rect_j.y0 - 2.0)
                elif abs(rect_i.y0 - rect_j.y0) <= 3.5 and rect_i.x0 < rect_j.x0:
                    if rect_i.x1 > rect_j.x0 - 2.0:
                        rect_i.x1 = min(rect_i.x1, rect_j.x0 - 2.0)
