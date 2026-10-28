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


class _FakeChatResponse:
    """sahte /chat/completions yanıtı; urlopen çağrılarını da sayar"""

    def __init__(self, content: str, finish_reason: str = "stop"):
        self._payload = {
            "choices": [{"message": {"content": content}, "finish_reason": finish_reason}]
        }
        self.calls = 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_length_finish_reason_means_truncated_and_returns_none(monkeypatch):
    # içerik dolu olsa bile finish_reason=length KESİK demektir: değer döndürülmez,
    # denemeler tükenince None + available=False + yedek uyarısı
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL, max_attempts=3)
    fake = _FakeChatResponse("kesilmis yarim ceviri", finish_reason="length")
    monkeypatch.setattr(lsb.urllib.request, "urlopen", fake)
    backend.available = True
    backend.model_id = "test-model"
    assert backend.translate_masked_text("uzun bir paragraf metni") is None
    assert fake.calls == 3  # kesik yanıt denemeye devam ettirdi, değilse kabul etmedi
    assert backend.available is False


def test_stop_finish_reason_with_content_is_returned(monkeypatch):
    fake = _FakeChatResponse("tam çeviri metni", finish_reason="stop")
    monkeypatch.setattr(lsb.urllib.request, "urlopen", fake)
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    backend.available = True
    backend.model_id = "test-model"
    assert backend.translate_masked_text("merhaba") == "tam çeviri metni"
    assert backend.available is True


def test_max_tokens_scales_with_long_input(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeChatResponse("uzun ceviri", finish_reason="stop")

    monkeypatch.setattr(lsb.urllib.request, "urlopen", fake_urlopen)
    backend = LMStudioBackend(base_url=DEAD_SERVER_URL)
    backend.available = True
    backend.model_id = "test-model"

    # kısa girdide alt sınır: 1024'ten küçük olamaz
    backend.translate_masked_text("kısa metin")
    assert captured["payload"]["max_tokens"] == 1024

    # uzun girdide ölçeklenir: 1024'ten büyük, 4096 üst sınırını aşmaz
    long_text = "kelime " * 800  # ~4800 karakter
    backend.available = True
    backend.translate_masked_text(long_text)
    assert 1024 < captured["payload"]["max_tokens"] <= 4096
