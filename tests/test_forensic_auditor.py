"""renderers/forensic_auditor.py adli denetim testleri."""
import pymupdf as fitz

from core.models import BoundingBox, ParagraphBlock
from renderers.forensic_auditor import PageForensicAuditor


def make_block(box: BoundingBox, text: str = "x") -> ParagraphBlock:
    return ParagraphBlock(id=0, page_num=0, box=box, text=text)


def test_audit_restores_lost_masks():
    masks = {"⟦CODE_0⟧": "clk", "⟦MTH_1⟧": "F = A + B"}
    repaired = PageForensicAuditor.audit_and_repair_translation(
        orig_text="The clk signal computes F = A + B.",
        trans_text="sinyal hesaplar",
        masks=masks,
    )
    assert "clk" in repaired
    assert "F = A + B" in repaired
    assert "CODE_" not in repaired and "MTH_" not in repaired


def test_audit_falls_back_to_original_on_severe_omission():
    original = "This is a fairly long English sentence that must survive translation without any loss."
    repaired = PageForensicAuditor.audit_and_repair_translation(original, "kisa", masks={})
    assert repaired == original


def test_audit_normalizes_orphan_brackets():
    repaired = PageForensicAuditor.audit_and_repair_translation("orig", "değer ﴾x﴿", masks={})
    assert "﴾" not in repaired and "(x)" in repaired


def test_zero_overlap_clamps_later_block_above_earlier_next_block():
    queue = [
        (make_block(BoundingBox(100, 100, 300, 120)), fitz.Rect(100, 100, 300, 200), "A", (0, 0, 0), (1, 1, 1)),
        (make_block(BoundingBox(100, 150, 300, 170)), fitz.Rect(100, 150, 300, 250), "B", (0, 0, 0), (1, 1, 1)),
    ]
    PageForensicAuditor.enforce_zero_overlap_geometry(queue, protected_rects=[])
    rect_a, rect_b = queue[0][1], queue[1][1]
    assert rect_a.y1 <= rect_b.y0 - 2.0


def test_zero_overlap_clamps_against_protected_rect():
    queue = [
        (make_block(BoundingBox(100, 100, 400, 120)), fitz.Rect(100, 100, 400, 200), "A", (0, 0, 0), (1, 1, 1)),
    ]
    protected = [fitz.Rect(380, 120, 500, 220)]
    PageForensicAuditor.enforce_zero_overlap_geometry(queue, protected_rects=protected)
    assert queue[0][1].y1 <= 118.0
