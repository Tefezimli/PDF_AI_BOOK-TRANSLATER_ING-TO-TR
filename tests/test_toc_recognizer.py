"""extractors/toc_recognizer.py İçindekiler tanıma testleri."""
from types import SimpleNamespace

from extractors.toc_recognizer import SpatialTOCRecognizer


class FakePage:
    """is_toc_or_index_page yalnızca get_text() ve rect.width kullanır."""

    rect = SimpleNamespace(width=612.0)

    def __init__(self, text: str):
        self._text = text

    def get_text(self, *args, **kwargs) -> str:
        return self._text


def toc_spans():
    spans = []
    rows = [
        ("Chapter 1 Introduction", "1"),
        ("1.1 Digital Systems Overview", "4"),
        ("1.2 Boolean Algebra and Gates", "17"),
        ("Appendix A VHDL Reference", "531"),
        ("Index", "588"),
    ]
    y = 100.0
    for title, num in rows:
        spans.append({"text": title, "bbox": (50.0, y, 300.0, y + 12.0), "size": 10.0, "flags": 0, "font": "Arial"})
        spans.append({"text": ".", "bbox": (302.0, y, 480.0, y + 12.0), "size": 10.0, "flags": 0, "font": "Arial"})
        spans.append({"text": num, "bbox": (520.0, y, 545.0, y + 12.0), "size": 10.0, "flags": 0, "font": "Arial"})
        y += 22.0
    return spans


def test_leader_dots_mark_toc_page():
    dotted = "\n".join(f"Section {i} ............ {i * 7}" for i in range(1, 6))
    assert SpatialTOCRecognizer.is_toc_or_index_page(FakePage(dotted), [], page_num=0)


def test_plain_body_page_is_not_toc():
    body = "The multiplexer selects one of the four inputs. Digital design fundamentals apply here."
    assert not SpatialTOCRecognizer.is_toc_or_index_page(FakePage(body), [], page_num=30)


def test_reconstruct_toc_rows_separates_titles_and_page_numbers():
    blocks = SpatialTOCRecognizer.reconstruct_toc_rows(9, toc_spans(), 612.0)
    assert blocks, "TOC satırları üretilmeli"

    titles = [b.text for b in blocks if not b.is_header_footer]
    page_nums = [b.text for b in blocks if b.is_header_footer]

    assert any("Chapter 1 Introduction" == t for t in titles)
    assert set(page_nums) >= {"1", "4", "17"}
    for t in titles:
        assert "..." not in t, f"nokta lideri temizlenmeli: {t!r}"
    for num_block in (b for b in blocks if b.is_header_footer):
        assert num_block.translated_text == num_block.text  # sayfa numaraları çevrilmez


def test_toc_rows_are_y_ordered():
    blocks = SpatialTOCRecognizer.reconstruct_toc_rows(9, toc_spans(), 612.0)
    ys = [b.box.y0 for b in blocks]
    assert ys == sorted(ys)
