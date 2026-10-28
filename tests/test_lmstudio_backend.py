"""translators/lmstudio_backend.py yerel LLM istemcisi testleri.

Gerçek bir LM Studio sunucusu gerektirmeden; kapalı port davranışı, ortam
değişkeni yapılandırması ve sahte sunucu yanıtıyla model tercihi sınanır.
"""
import json

import translators.lmstudio_backend as lsb
from translators.lmstudio_backend import LMStudioBackend

DEAD_SERVER_URL = "http://127.0.0.1:1/v1"  # port 1: anında bağlantı reddi


def test_unreachable_server_marks_backend_unavailable():
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    assert backend.available is False


def test_translate_returns_none_when_server_down():
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    assert backend.translate_masked_text("merhaba dünya") is None


def test_set_domain_updates_prompt_label():
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    backend.set_domain("Tıp ve Sağlık Bilimleri")
    assert backend.domain_label == "Tıp ve Sağlık Bilimleri"


def test_env_url_override(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_URL", "http://127.0.0.1:9999/v1/")
    assert LMStudioBackend().base_url == "http://127.0.0.1:9999/v1"


def test_env_port_override(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_PORT", "1235")
    monkeypatch.delenv("PDF_AI_LMSTUDIO_URL", raising=False)
    assert LMStudioBackend().base_url == "http://localhost:1235/v1"


def test_explicit_url_beats_env(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_URL", "http://from-env:1/v1")
    assert LMStudioBackend(base_url=DEAD_SERVER_URL).base_url == DEAD_SERVER_URL


def test_env_timeout_values(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_TIMEOUT", "90")
    monkeypatch.setenv("PDF_AI_LMSTUDIO_CHECK_TIMEOUT", "geçersiz")
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    assert backend.request_timeout == 90.0
    assert backend.check_timeout == 2.0  # bozuk değer varsayılana düşer


def test_env_attempts(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_ATTEMPTS", "3")
    assert LMStudioBackend(base_url=DEAD_SERVER_URL).max_attempts == 3


class _FakeResponse:
    """tek model listesi döndüren sahte /models yanıtı"""

    MODELS = [{"id": "mistral-7b-instruct"}, {"id": "TheRains/Qwen2.5-14B-Instruct-Q4_K_M-GGUF"}]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"data": self.MODELS}).encode("utf-8")


def test_model_preference_from_env(monkeypatch):
    monkeypatch.setenv("PDF_AI_LMSTUDIO_MODEL", "qwen2.5")
    monkeypatch.setattr(lsb.urllib.request, "urlopen", lambda req, timeout=None: _FakeResponse())
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)  # sahte yanıt nedeniyle gerçek adrese bakılır
    assert backend.available is True
    assert backend.model_id == "TheRains/Qwen2.5-14B-Instruct-Q4_K_M-GGUF"


def test_model_fallback_first_when_no_preference(monkeypatch):
    monkeypatch.delenv("PDF_AI_LMSTUDIO_MODEL", raising=False)
    monkeypatch.setattr(lsb.urllib.request, "urlopen", lambda req, timeout=None: _FakeResponse())
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    assert backend.model_id == "mistral-7b-instruct"
