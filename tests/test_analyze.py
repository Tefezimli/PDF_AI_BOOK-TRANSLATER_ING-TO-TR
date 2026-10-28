"""run_analysis / --analyze ön analiz raporu testleri (gerçek PDF üzerinde)."""
import pymupdf as fitz

import pdf_bridge
from pdf_bridge import run_analysis


def build_mixed_pdf(path, pages=2):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 24), f"Chapter {i + 1}")                       # üst bilgi bölgesi
        page.insert_text((72, 120), "The multiplexer selects one input signal.")  # düz metin
        page.insert_text((72, 160), "signal q_reg : std_logic_vector(7 downto 0);")  # VHDL kodu
    doc.save(path)
    doc.close()


def test_analysis_counts_on_real_pdf(tmp_path):
    pdf = tmp_path / "karisik.pdf"
    build_mixed_pdf(str(pdf))

    lines = []
    stats = run_analysis(str(pdf), allow_ocr=False, print_fn=lines.append)

    assert stats["analyzed_pages"] == 2
    assert stats["blocks"] == stats["prose"] + stats["code"] + stats["math"] + stats["header_footer"]
    assert stats["code"] >= 2, "VHDL satırları kod karantinasına girmeli"
    assert stats["prose"] >= 2, "düz metin blokları sayılmalı"
    assert any("Kod karantina" in ln for ln in lines)


def test_analysis_respects_page_selection(tmp_path):
    pdf = tmp_path / "karisik.pdf"
    build_mixed_pdf(str(pdf), pages=3)

    stats = run_analysis(str(pdf), allow_ocr=False, pages=[0], print_fn=lambda s: None)
    assert stats["analyzed_pages"] == 1
    assert stats["total_pages"] == 3


def test_analysis_is_read_only(tmp_path):
    """Analiz çıktı/checkpoint dosyası üretmemeli."""
    pdf = tmp_path / "karisik.pdf"
    build_mixed_pdf(str(pdf))
    before = sorted(p.name for p in tmp_path.iterdir())

    run_analysis(str(pdf), allow_ocr=False, print_fn=lambda s: None)

    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after


def test_main_analyze_flag_short_circuits_pipeline(tmp_path, monkeypatch):
    pdf = tmp_path / "karisik.pdf"
    build_mixed_pdf(str(pdf))
    monkeypatch.setattr(
        pdf_bridge, "run_pipeline",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("analyze cevirmemeli"))
    )
    rc = pdf_bridge.main([str(pdf), "--analyze"])
    assert rc == 0
