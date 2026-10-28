"""parse_page_selection ve --pages kablolama testleri."""
import pytest

import pdf_bridge
from pdf_bridge import is_full_page_selection, parse_page_selection


def test_single_page():
    assert parse_page_selection("3", 10) == [2]


def test_range():
    assert parse_page_selection("1-3", 10) == [0, 1, 2]


def test_mixed_list_deduplicates_and_sorts():
    assert parse_page_selection("5,1-3,2,10", 10) == [0, 1, 2, 4, 9]


def test_spaces_tolerated():
    assert parse_page_selection(" 1 - 3 , 5 ", 10) == [0, 1, 2, 4]


def test_out_of_range_dropped():
    assert parse_page_selection("8-15", 10) == [7, 8, 9]


def test_full_page_count_selectable():
    assert parse_page_selection("1-10", 10) == list(range(10))


def test_huge_range_clamped_without_oom():
    # '1-1000000000' milyarlarca int üreterek RAM'i kilitlememeli;
    # anında toplam sayfaya clamp'lenip dokümanın tamamını döndürmeli (< 1 sn).
    assert parse_page_selection("1-1000000000", 10) == list(range(10))


@pytest.mark.parametrize("bad", ["", "0", "1-", "a", "3-1", "2-"])
def test_invalid_specs_raise(bad):
    with pytest.raises(ValueError):
        parse_page_selection(bad, 10)


def test_trailing_comma_tolerated():
    assert parse_page_selection("1,,", 10) == [0]


# --- is_full_page_selection: kısmi koşuda checkpoint silinme kararı ---
def test_is_full_page_selection_true_for_all_pages():
    assert is_full_page_selection([0, 1, 2], 3) is True
    assert is_full_page_selection(list(range(5)), 5) is True


def test_is_full_page_selection_false_for_partial():
    assert is_full_page_selection([0, 1], 3) is False
    assert is_full_page_selection([], 3) is False
    assert is_full_page_selection([0, 1, 2], 4) is False


def test_is_full_page_selection_ignores_order():
    assert is_full_page_selection([2, 0, 1], 3) is True


def test_main_passes_pages_to_pipeline(tmp_path, monkeypatch):
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    import pymupdf as fitz
    doc = fitz.open()
    for _ in range(4):
        doc.new_page()
    doc.save(str(src))
    doc.close()

    calls = {}
    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda i, o, **kw: calls.update(inp=i, out=o, **kw))
    rc = pdf_bridge.main([str(src), "--pages", "2-3"])
    assert rc == 0
    assert calls["pages"] == [1, 2]


def test_main_pages_suffix_in_default_output(tmp_path, monkeypatch):
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    import pymupdf as fitz
    doc = fitz.open()
    for _ in range(4):
        doc.new_page()
    doc.save(str(src))
    doc.close()

    calls = {}
    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda i, o, **kw: calls.update(out=o))
    rc = pdf_bridge.main([str(src), "--pages", "1-2"])
    assert rc == 0
    assert calls["out"].endswith("kitap_p1-2_ULTIMATE.pdf")


def test_main_invalid_pages_returns_error(tmp_path, monkeypatch, capsys):
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    import pymupdf as fitz
    doc = fitz.open()
    doc.new_page()
    doc.save(str(src))
    doc.close()

    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda *a, **k: (_ for _ in ()).throw(AssertionError("cagirilmamali")))
    rc = pdf_bridge.main([str(src), "--pages", "9-9"])
    assert rc != 0
