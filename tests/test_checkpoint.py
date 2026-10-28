"""core/checkpoint.py mizanpaj checkpoint testleri.

Çökme/yeniden başlatma senaryoları dosya düzeyinde simüle edilir; motor veya
AI bağımlılığı gerekmez.
"""
import dataclasses
import json
import os
import time

from core.checkpoint import (
    ExtractionCheckpoint,
    block_from_dict,
    block_to_dict,
    document_fingerprint,
)
from core.models import BoundingBox, ParagraphBlock


def make_block(**overrides) -> ParagraphBlock:
    fields = dict(
        id=7,
        page_num=3,
        box=BoundingBox(10.0, 20.0, 300.0, 340.0),
        text="entity counter is",
        translated_text="",
        font_size=9.5,
        is_standalone_math=False,
        is_code_block=True,
        is_header_footer=False,
        is_from_ocr=False,
        is_bold=True,
        is_centered=False,
        is_table_or_diagram_cell=False,
        text_color=(0.1, 0.2, 0.3),
        bg_color=(1.0, 1.0, 1.0),
        max_allowed_y1=350.0,
        max_allowed_x1=310.0,
    )
    fields.update(overrides)
    return ParagraphBlock(**fields)


def make_pdf(tmp_path, name="kitap.pdf", content=b"%PDF-1.4 test icerik"):
    p = tmp_path / name
    p.write_bytes(content)
    return str(p)


def test_block_roundtrip_preserves_all_fields():
    block = make_block()
    restored = block_from_dict(block_to_dict(block))
    assert dataclasses.asdict(restored) == dataclasses.asdict(block)
    assert isinstance(restored.box, BoundingBox)
    assert isinstance(restored.text_color, tuple)


def test_fingerprint_changes_with_content(tmp_path):
    pdf = make_pdf(tmp_path)
    fp1 = document_fingerprint(pdf)
    with open(pdf, "ab") as f:
        f.write(b"ek icerik")
    fp2 = document_fingerprint(pdf)
    assert fp1 != fp2


def test_fingerprint_stable_for_same_file(tmp_path):
    pdf = make_pdf(tmp_path)
    assert document_fingerprint(pdf) == document_fingerprint(pdf)


def test_resume_across_instances(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)

    first = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=5, checkpoint_dir=ckpt_dir)
    first.add_page(0, [make_block(text="page zero")])
    first.add_page(2, [make_block(text="page two"), make_block(text="second block")])

    second = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=5, checkpoint_dir=ckpt_dir)
    assert second.has_page(0) and second.has_page(2)
    assert not second.has_page(1) and not second.has_page(3)
    assert [b.text for b in second.get_page(0)] == ["page zero"]
    assert second.get_page(2)[1].text == "second block"
    assert second.get_page(2)[1].box.x0 == 10.0


def test_crashed_partial_line_is_ignored(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)

    first = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    first.add_page(0, [make_block(text="tamamlanan sayfa")])

    # Çökme simülasyonu: dosyaya yarım JSON satırı düşmüş olsun
    with open(first.path, "a", encoding="utf-8") as f:
        f.write('{"page": 1, "blocks": [{"id": 9, "page_num"')

    second = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    assert second.has_page(0)
    assert not second.has_page(1)  # yarım satır yok sayıldı, sayfa yeniden analiz edilecek


def test_changed_input_invalidates_checkpoint(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)

    first = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    first.add_page(0, [make_block(text="eski icerik")])

    with open(pdf, "ab") as f:
        f.write(b"degisiklik")
    time.sleep(0.01)

    second = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    assert not second.has_page(0)  # parmak izi uyuşmadı → sıfırdan


def test_resume_false_forces_fresh_start(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)

    first = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    first.add_page(0, [make_block(text="onceki deneme")])

    second = ExtractionCheckpoint.create_or_load(
        pdf, allow_ocr=True, total_pages=3, resume=False, checkpoint_dir=ckpt_dir
    )
    assert not second.has_page(0)


def test_allow_ocr_flag_changes_checkpoint_identity(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)

    a = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    a.add_page(0, [make_block(text="ocr'li")])
    b = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=False, total_pages=3, checkpoint_dir=ckpt_dir)
    assert not b.has_page(0)  # farklı mod farklı dosya
    assert a.path != b.path


def test_discard_removes_file(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)

    ckpt = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=3, checkpoint_dir=ckpt_dir)
    ckpt.add_page(0, [make_block()])
    assert os.path.exists(ckpt.path)

    ckpt.discard()
    assert not os.path.exists(ckpt.path)
    ckpt.discard()  # idempotent


def test_header_is_valid_json_with_fingerprint(tmp_path):
    ckpt_dir = str(tmp_path / "ck")
    pdf = make_pdf(tmp_path)
    ckpt = ExtractionCheckpoint.create_or_load(pdf, allow_ocr=True, total_pages=9, checkpoint_dir=ckpt_dir)

    with open(ckpt.path, "r", encoding="utf-8") as f:
        header = json.loads(f.readline())
    assert header["total_pages"] == 9
    assert header["fingerprint"] == document_fingerprint(pdf)
