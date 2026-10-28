"""GUI ayarlarının kalıcı hali (build/gui_settings.json).

Ayarlar hem arayüzde hem CLI/env tarafında aynı anlama gelir:
  - lmstudio_url / lmstudio_port / lmstudio_model -> PDF_AI_LMSTUDIO_* env
  - allow_ocr, pages, fresh                      -> run_pipeline kwarg'ları
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

SETTINGS_PATH = os.path.join("build", "gui_settings.json")

DEFAULTS: Dict[str, Any] = {
    "lmstudio_url": "",    # boş = port'tan türetilir (http://localhost:<port>/v1)
    "lmstudio_port": "1234",
    "lmstudio_model": "",  # boş = sunucunun listedeki ilk modeli
    "allow_ocr": True,     # taranmış sayfalarda Tesseract OCR
    "pages": "",           # boş = tüm sayfalar; örnek: "1-10", "1,2,5-8"
    "fresh": False,        # True = checkpoint'i yok say, sıfırdan başla
}


def load_settings(path: str = SETTINGS_PATH) -> Dict[str, Any]:
    data = dict(DEFAULTS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key in DEFAULTS:
                    if key in loaded:
                        data[key] = loaded[key]
        except Exception:
            pass  # bozuksa varsayılanlarla devam
    return data


def save_settings(settings: Dict[str, Any], path: str = SETTINGS_PATH) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def apply_lmstudio_env(settings: Dict[str, Any]) -> None:
    """LM Studio adres/model tercihini süreç env'ine yazar.

    GUI alanı boş bırakıldıysa ilgili env temizlenir ki varsayılanlar
    (localhost:1234, ilk model) devreye girsin — dışarıdan setting edilmiş
    değişken GUI açıkken GUI'nin sahipliğiyle yönetilir.
    """
    url = str(settings.get("lmstudio_url", "")).strip()
    port = str(settings.get("lmstudio_port", "")).strip()
    model = str(settings.get("lmstudio_model", "")).strip()

    if url:
        os.environ["PDF_AI_LMSTUDIO_URL"] = url
    else:
        os.environ.pop("PDF_AI_LMSTUDIO_URL", None)

    if port:
        os.environ["PDF_AI_LMSTUDIO_PORT"] = port

    if model:
        os.environ["PDF_AI_LMSTUDIO_MODEL"] = model
    else:
        os.environ.pop("PDF_AI_LMSTUDIO_MODEL", None)
