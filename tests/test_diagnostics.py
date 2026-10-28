"""core/diagnostics.py ortam tanılama testleri."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.diagnostics import (
    FAIL,
    OK,
    WARN,
    check_import,
    check_lmstudio,
    check_translation_cache,
    run_doctor,
)


def test_check_import_installed():
    status, label, _ = check_import("pymupdf")
    assert status == OK
    assert "pymupdf" in label


def test_check_import_missing():
    status, _, _ = check_import("kesin_yok_olan_modul_xyz")
    assert status == FAIL


def test_cache_check_clean(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"__version__": "v", "a": "merhaba"}), encoding="utf-8")
    status, _, detail = check_translation_cache(str(p))
    assert status == OK
    assert "1 ceviri" in detail
    assert "0 kirli" in detail


def test_cache_check_contaminated(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"__version__": "v", "a": "ceviri CODE_0 kalmis"}), encoding="utf-8")
    _, _, detail = check_translation_cache(str(p))
    assert "1 kirli" in detail


def test_cache_check_absent(tmp_path):
    status, _, _ = check_translation_cache(str(tmp_path / "yok.json"))
    assert status == OK


class _ModelsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": [{"id": "qwen2.5-7b-instruct"}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_lmstudio_check_reachable(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _ModelsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("PDF_AI_LMSTUDIO_URL", f"http://127.0.0.1:{server.server_port}/v1")
        status, _, detail = check_lmstudio()
        assert status == OK
        assert "qwen2.5-7b-instruct" in detail
    finally:
        server.shutdown()


def test_lmstudio_check_unreachable(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_URL", "http://127.0.0.1:9/v1")
    status, _, detail = check_lmstudio()
    assert status == WARN
    assert "erisilemiyor" in detail


def test_run_doctor_exit_codes():
    lines = []
    rc = run_doctor(checks=[lambda: (OK, "iyi", "detay"), lambda: (WARN, "uyari", "detay")], print_fn=lines.append)
    assert rc == 0
    assert any("0 hata, 1 uyari" in ln for ln in lines)

    rc = run_doctor(checks=[lambda: (FAIL, "kotu", "detay")], print_fn=lines.append)
    assert rc == 1
