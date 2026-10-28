"""pdf_bridge ProgressReporter kanalı testleri."""
from pdf_bridge import ProgressReporter


def test_emit_delivers_event_and_detail_dict():
    received = []
    reporter = ProgressReporter(lambda event, detail: received.append((event, detail)))
    reporter.emit("progress", done=3, total=10)
    assert received == [("progress", {"done": 3, "total": 10})]


def test_emit_swallows_callback_errors():
    def broken_cb(event, detail):
        raise RuntimeError("GUI patladı")

    reporter = ProgressReporter(broken_cb)
    reporter.emit("stage", stage=1)  # boru hattını durdurmamalı


def test_noop_without_callback():
    reporter = ProgressReporter()
    reporter.emit("done", output_pdf="x.pdf")  # sessiz no-op


def test_pipeline_contract_events():
    """GUI'nin beklediği olay şemasını kilitleyen sözleşme testi."""
    received = []
    reporter = ProgressReporter(lambda e, d: received.append(e))
    for event, kwargs in [
        ("stage", dict(stage=1, label="x", percent=8.0)),
        ("progress", dict(done=1, total=4)),
        ("stage", dict(stage=3, label="y", percent=85.0)),
        ("stage", dict(stage=4, label="z", percent=92.0)),
        ("done", dict(output_pdf="o.pdf", clean_txt="t.txt", review_txt="r.txt")),
    ]:
        reporter.emit(event, **kwargs)
    assert received == ["stage", "progress", "stage", "stage", "done"]
