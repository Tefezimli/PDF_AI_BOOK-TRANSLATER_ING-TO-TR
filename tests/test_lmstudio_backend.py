"""translators/lmstudio_backend.py yerel LLM istemcisi testleri.

Gerçek bir LM Studio sunucusu gerektirmeden yalnızca kapalı port / etki alanı
ayarı gibi istemci tarafı davranışlar sınanır.
"""
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
