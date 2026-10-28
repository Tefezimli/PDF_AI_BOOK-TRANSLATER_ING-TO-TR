"""Güvenlik yamaları: OOM clamp'i, atomik cache, şifreli PDF, kısmi koşu checkpoint'ı."""
import pymupdf as fitz
import pytest

import pdf_bridge
from pdf_bridge import open_input_document, parse_page_selection
from translators.cache_manager import SelfHealingCache


# --- parse_page_selection: OOM koruması ---
def test_huge_range_is_clamped_not_expanded():
    # 1-1000000000 RAM'i kilitlememeli; anında clamp'lenip dönmeli
    assert parse_page_selection("1-1000000000", 10) == list(range(10))


def test_out_of_range_warns_and_drops(capsys):
    assert parse_page_selection("8-15", 10) == [7, 8, 9]
    assert "aralik disinda" in capsys.readouterr().out


def test_fully_out_of_range_raises():
    with pytest.raises(ValueError):
        parse_page_selection("15-20", 10)


# --- atomik cache yazımı ---
def test_cache_save_is_atomic_on_failure(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    cache = SelfHealingCache(str(cache_file))
    cache.put("k", "eski deger")
    assert cache.save()

    # Çökme simülasyonu: json.dump yazım ortasında patlasın
    import translators.cache_manager as cm

    def broken_dump(*a, **k):
        a[0].write('{"yarim": ')  # yarım yaz
        raise RuntimeError("crash")

    monkeypatch.setattr(cm.json, "dump", broken_dump)
    assert cache.save() is False

    # Eski dosya sağlam ve .tmp kalıntısı yok
    healed = SelfHealingCache(str(cache_file))
    assert healed.get("k") == "eski deger"
    assert not (tmp_path / "cache.json.tmp").exists()


def test_cache_save_leaves_no_tmp_on_success(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache = SelfHealingCache(str(cache_file))
    cache.put("a", "b")
    assert cache.save()
    assert not (tmp_path / "cache.json.tmp").exists()
    assert SelfHealingCache(str(cache_file)).get("a") == "b"


# --- şifreli PDF koruması ---
def test_encrypted_pdf_rejected_with_clear_error(tmp_path):
    doc = fitz.open()
    doc.new_page()
    enc = str(tmp_path / "sifreli.pdf")
    doc.save(enc, encryption=fitz.PDF_ENCRYPT_AES_128, user_pw="gizli")
    doc.close()

    with pytest.raises(ValueError, match="sifreli"):
        open_input_document(enc)


def test_plain_pdf_opens(tmp_path):
    p = str(tmp_path / "duz.pdf")
    doc = fitz.open()
    doc.new_page()
    doc.save(p)
    doc.close()
    opened = open_input_document(p)
    assert len(opened) == 1
    opened.close()


# --- kısmi koşu checkpoint'i koruma kararı (saf mantık) ---
def test_partial_pages_do_not_discard_checkpoint(tmp_path, monkeypatch):
    """--pages ile koşan boru hattı checkpoint.discard çağırmamalı."""
    src = tmp_path / "kitap.pdf"
    doc = fitz.open()
    for _ in range(4):
        doc.new_page()
    doc.save(str(src))
    doc.close()

    discard_calls = []

    class FakeCheckpoint:
        def __init__(self, *a, **k):
            pass

        @classmethod
        def create_or_load(cls, *a, **k):
            return cls()

        def has_page(self, n):
            return False

        def get_page(self, n):
            return []

        def add_page(self, n, blocks):
            pass

        def discard(self):
            discard_calls.append(1)

    monkeypatch.setattr(pdf_bridge, "ExtractionCheckpoint", FakeCheckpoint)
    monkeypatch.setattr(pdf_bridge, "run_cpp_layout_engine", lambda *a, **k: None)
    monkeypatch.setattr(pdf_bridge, "select_best_unicode_fonts", lambda: ("", "", None))
    monkeypatch.setattr(
        pdf_bridge, "RedactionPDFRenderer",
        lambda *a, **k: type("R", (), {"render_document": staticmethod(lambda *a, **k: None)})()
    )
    monkeypatch.setattr(pdf_bridge, "export_copyable_txt_files", lambda *a, **k: None)
    monkeypatch.setattr(pdf_bridge, "get_safe_device", lambda: (object(), object()))
    monkeypatch.setattr(pdf_bridge, "release_memory", lambda *a, **k: None)

    from core.models import ParagraphBlock, BoundingBox

    # çeviri motoru yerine kimlik döndüren sahte (translate_block çağrılmayacak:
    # extract_paragraphs da sahtelenir)
    class FakeEngine:
        allow_ocr = False

        def extract_paragraphs(self, page, n):
            return [ParagraphBlock(id=0, page_num=n, box=BoundingBox(1, 1, 2, 2), text="x")]

    monkeypatch.setattr(pdf_bridge, "GeometricLayoutEngine", lambda **k: FakeEngine())
    monkeypatch.setattr(pdf_bridge, "UniversalTranslationEngine", lambda *a, **k: type(
        "T", (), {"profile_book_domain": staticmethod(lambda doc: None),
                  "translate_block": staticmethod(lambda p: p.text),
                  "save_cache": staticmethod(lambda: True)})()
    )

    out = tmp_path / "cikti.pdf"
    pdf_bridge.run_pipeline(str(src), str(out), pages=[0, 1], resume=False)
    assert discard_calls == [], "kismi kosu checkpoint'i silmemeli"
