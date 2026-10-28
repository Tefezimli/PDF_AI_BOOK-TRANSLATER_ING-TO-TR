"""pdf_bridge komut satırı arayüzü testleri (argparse katmanı)."""
import pdf_bridge


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
