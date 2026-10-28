"""core/user_settings.py kalıcı GUI ayarları testleri."""
import json

from core.user_settings import DEFAULTS, apply_lmstudio_env, load_settings, save_settings


def test_defaults_when_file_missing(tmp_path):
    s = load_settings(str(tmp_path / "yok.json"))
    assert s == DEFAULTS
    assert s["lmstudio_port"] == "1234"
    assert s["allow_ocr"] is True


def test_save_and_reload_roundtrip(tmp_path):
    path = str(tmp_path / "gui_settings.json")
    custom = dict(DEFAULTS, lmstudio_port="1235", lmstudio_model="qwen2.5-7b", pages="1-10", fresh=True)
    assert save_settings(custom, path)
    assert load_settings(path) == custom


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "gui_settings.json"
    path.write_text("{bozuk json", encoding="utf-8")
    assert load_settings(str(path)) == DEFAULTS


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "gui_settings.json"
    payload = dict(DEFAULTS)
    payload["bilinmeyen_alan"] = "x"
    payload["pages"] = "3-5"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_settings(str(path))
    assert "bilinmeyen_alan" not in loaded
    assert loaded["pages"] == "3-5"


def test_apply_env_sets_and_clears(monkeypatch):
    monkeypatch.delenv("PDF_AI_LMSTUDIO_URL", raising=False)
    monkeypatch.delenv("PDF_AI_LMSTUDIO_MODEL", raising=False)

    apply_lmstudio_env(dict(DEFAULTS, lmstudio_url="http://10.0.0.2:8080/v1", lmstudio_model="qwen2.5-7b"))
    import os
    assert os.environ["PDF_AI_LMSTUDIO_URL"] == "http://10.0.0.2:8080/v1"
    assert os.environ["PDF_AI_LMSTUDIO_MODEL"] == "qwen2.5-7b"

    # Alanlar boşaltılınca env temizlenir → varsayılanlar devreye girer
    apply_lmstudio_env(dict(DEFAULTS))
    assert "PDF_AI_LMSTUDIO_URL" not in os.environ
    assert "PDF_AI_LMSTUDIO_MODEL" not in os.environ


def test_apply_env_port_only(monkeypatch):
    monkeypatch.delenv("PDF_AI_LMSTUDIO_URL", raising=False)
    apply_lmstudio_env(dict(DEFAULTS, lmstudio_port="1235"))
    import os
    assert os.environ["PDF_AI_LMSTUDIO_PORT"] == "1235"
    assert "PDF_AI_LMSTUDIO_URL" not in os.environ
