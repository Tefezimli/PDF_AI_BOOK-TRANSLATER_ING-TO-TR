import os
import gc
import shutil
from typing import Tuple
import torch
import pytesseract


def configure_tesseract() -> bool:
    which_tess = shutil.which("tesseract")
    if which_tess and os.path.exists(which_tess):
        pytesseract.pytesseract.tesseract_cmd = which_tess
        return True
    for path in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tesseract-OCR", "tesseract.exe"),
    ]:
        if path and os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True
    return False


HAS_TESSERACT = configure_tesseract()


def get_safe_device() -> Tuple[torch.device, torch.dtype]:
    if torch.cuda.is_available():
        try:
            cap = torch.cuda.get_device_capability(0)
            gpu_name = torch.cuda.get_device_name(0)
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

            test_tensor = torch.tensor([[1.0, 2.0], [3.0, 4.0]], device="cuda", dtype=dtype)
            _ = torch.matmul(test_tensor, test_tensor)
            torch.cuda.synchronize()

            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.set_float32_matmul_precision("high")

            print(f"[DONANIM] GPU Aktif: {gpu_name} (Mimari: sm_{cap[0]}{cap[1]} | Mod: {dtype})")
            return torch.device("cuda"), dtype
        except Exception as e:
            print(f"[DONANIM UYARISI] GPU kernel/mimari uyumsuzlugu ({e}). Guvenli CPU moduna geciliyor.")
    else:
        if getattr(torch.version, "cuda", None) is None:
            print(
                "[DONANIM TESHISI] Sistemde 'CPU-Only' PyTorch kurulu oldugu icin NVIDIA ekran karti kullanilamiyor.\n"
                "  -> GPU'yu aktif etmek icin: pip install torch --index-url https://download.pytorch.org/whl/cu124"
            )

    cpu_threads = max(1, (os.cpu_count() or 4) - 1)
    torch.set_num_threads(cpu_threads)
    print(f"[DONANIM] Stabil CPU Modu Aktif ({cpu_threads} Thread).")
    return torch.device("cpu"), torch.float32


def release_memory(device: torch.device) -> None:
    if device.type == "cuda":
        try:
            torch.cuda.empty_cache()
        except Exception:
            _ = None
    gc.collect()
