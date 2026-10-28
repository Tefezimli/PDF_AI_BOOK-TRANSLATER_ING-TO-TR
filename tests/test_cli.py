"""pdf_bridge komut satırı arayüzü testleri (argparse katmanı + main())."""
import pytest

import pdf_bridge


def test_version_flag(capsys):
    try:
        pdf_bridge.build_arg_parser().parse_args(["--version"])
        assert False, "argparse SystemExit vermeli"
    except SystemExit as e:
        assert e.code == 0
    assert pdf_bridge.__version__ in capsys.readouterr().out


def test_defaults():
    args = pdf_bridge.build_arg_parser().parse_args(["kitap.pdf"])
    assert args.input_pdf == "kitap.pdf"
    assert args.output_pdf is None
    assert args.no_ocr is False


def test_output_override():
    args = pdf_bridge.build_arg_parser().parse_args(["kitap.pdf", "-o", "cikti.pdf"])
    assert args.output_pdf == "cikti.pdf"


def test_no_ocr_flag():
    args = pdf_bridge.build_arg_parser().parse_args(["kitap.pdf", "--no-ocr"])
    assert args.no_ocr is True


def test_fresh_flag_defaults_false():
    args = pdf_bridge.build_arg_parser().parse_args(["kitap.pdf"])
    assert args.fresh is False
    args = pdf_bridge.build_arg_parser().parse_args(["kitap.pdf", "--fresh"])
    assert args.fresh is True


def test_main_passes_resume_flags(tmp_path, monkeypatch):
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    calls = {}
    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda i, o, **kw: calls.update(**kw))

    pdf_bridge.main([str(src)])
    assert calls["resume"] is True

    pdf_bridge.main([str(src), "--fresh"])
    assert calls["resume"] is False


def test_main_invokes_pipeline_with_default_output(tmp_path, monkeypatch):
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    calls = {}
    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda i, o, **kw: calls.update(inp=i, out=o, **kw))

    rc = pdf_bridge.main([str(src)])
    assert rc == 0
    assert calls["inp"] == str(src)
    assert calls["out"].endswith("kitap_ULTIMATE.pdf")
    assert calls["allow_ocr"] is True


def test_main_respects_output_and_no_ocr(tmp_path, monkeypatch):
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    calls = {}
    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda i, o, **kw: calls.update(inp=i, out=o, **kw))

    rc = pdf_bridge.main([str(src), "-o", "cikti.pdf", "--no-ocr"])
    assert rc == 0
    assert calls["out"] == "cikti.pdf"
    assert calls["allow_ocr"] is False


def test_main_missing_input_returns_error_code(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pdf_bridge, "run_pipeline", lambda *a, **k: (_ for _ in ()).throw(AssertionError("çağrılmamalı")))
    rc = pdf_bridge.main([str(tmp_path / "yok.pdf")])
    assert rc == 1
    assert "bulunamadi" in capsys.readouterr().out


def test_main_reports_runtime_error_cleanly(tmp_path, monkeypatch, capsys):
    """Şifreli/bozuk PDF hataları CLI'da traceback yerine tek satır [HATA] olmalı."""
    src = tmp_path / "kitap.pdf"
    src.write_bytes(b"%PDF-1.4 test")

    def boom(*a, **k):
        raise RuntimeError("PDF sifreli/korumali; sifresiz bir kopya ile tekrar deneyin.")

    monkeypatch.setattr(pdf_bridge, "run_pipeline", boom)
    rc = pdf_bridge.main([str(src)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[HATA]" in out
    assert "sifresiz bir kopya" in out


def test_open_input_document_rejects_corrupt_pdf(tmp_path):
    bad = tmp_path / "bozuk.pdf"
    bad.write_bytes(b"bu bir pdf degil")
    with pytest.raises(RuntimeError, match="bozuk"):
        pdf_bridge.open_input_document(str(bad))
