"""Test ortamı köprüsü.

Projenin saf mantık katmanlarını (sanitizer, formalism, TOC, cache, LM Studio
istemcisi) ağır AI bağımlılıkları olmadan test edebilmek için eksik kütüphanelere
minimal yedek modüller takar. PyTorch/OpenCV kurulu makinelerde gerçek
kütüphaneler kullanılır; yedekler yalnızca eksikse devreye girer.
"""
import importlib.util
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_stub(name: str, **attrs) -> None:
    if importlib.util.find_spec(name) is not None:
        return
    mod = types.ModuleType(name)
    for key, val in attrs.items():
        setattr(mod, key, val)
    mod.__getattr__ = lambda item: object()  # çalışma anı sembolleri için nötr yedek
    sys.modules[name] = mod


# torch.device / torch.dtype tip anotasyonları import anında değerlendiği için
# stub'da bu iki sembol gerçek nesne olmak zorunda.
_install_stub("torch", device=object, dtype=object)
# cv2 ve transformers yalnızca fonksiyon içinde kullanılır; nötr yedek yeterli.
_install_stub("cv2")
_install_stub("transformers")

if importlib.util.find_spec("pytesseract") is None:
    tess = types.ModuleType("pytesseract")
    tess.pytesseract = types.SimpleNamespace(tesseract_cmd="")
    sys.modules["pytesseract"] = tess
