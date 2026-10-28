"""Ortam tanılama raporu (`pdfai-translate --doctor`).

Ağır AI bağımlılıkları eksik ortamlarda da import edilebilir: eksik paketler
durum satırı olarak raporlanır, asla ImportError ile çökmez. Kontroller
salt-okunurdur (önbellek otomatik onarılmaz, checkpoint silinmez).
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
import urllib.request
from typing import Callable, List, Tuple

from core.paths import build_dir

# (durum, etiket) çifti; durum: OK | WARN | FAIL
CheckResult = Tuple[str, str, str]

OK, WARN, FAIL = "OK", "UYARI", "HATA"

# Kritik: bunlarsız boru hattı hiç çalışmaz (doctor çıkış kodunu 1 yapar).
CORE_MODULES = ["pymupdf"]
# AI stack'i: yoksa WARN ([ai] extra'sı ile kurulur).
AI_MODULES = ["torch", "transformers", "cv2"]
# OCR zinciri: yoksa taranmış sayfalar atlanır/dijital akış çalışır.
AUX_MODULES = ["PIL", "numpy", "pytesseract"]


def check_import(name: str) -> CheckResult:
    if importlib.util.find_spec(name) is not None:
        return OK, f"Python paketi: {name}", "kurulu"
    return FAIL, f"Python paketi: {name}", "kurulu degil (pip install)"


def check_python() -> CheckResult:
    v = sys.version_info[:2]
    if v >= (3, 10):
        return OK, "Python surumu", platform.python_version()
    return FAIL, "Python surumu", f"{platform.python_version()} (3.10+ gerekli)"


def check_tesseract() -> CheckResult:
    try:
        from core.hardware import HAS_TESSERACT
        if HAS_TESSERACT:
            return OK, "Tesseract OCR", "bulundu (taranmis sayfalar desteklenir)"
        return WARN, "Tesseract OCR", "bulunamadi; taranmis sayfalar islenmez, dijital PDF'ler etkilenmez"
    except Exception as exc:
        return WARN, "Tesseract OCR", f"kontrol edilemedi: {exc}"


def check_turkish_font() -> CheckResult:
    try:
        from core.unicode_sanitizer import select_best_unicode_fonts
        reg, _, _ = select_best_unicode_fonts()
        if reg:
            return OK, "Turkce font", os.path.basename(reg)
        return WARN, "Turkce font", (
            "sistemde bulunamadi; cikti dahili 'helv' fontuna duser (Turkce glifler bozulur). "
            "PDF_AI_FONT_REGULAR ile TTF zorlanabilir."
        )
    except Exception as exc:
        return WARN, "Turkce font", f"kontrol edilemedi: {exc}"


def check_lmstudio(check_timeout: float = 2.0) -> CheckResult:
    try:
        from translators.lmstudio_backend import _resolve_base_url
    except Exception as exc:
        return WARN, "LM Studio", f"istemci modulu yuklenemedi: {exc}"

    base_url = _resolve_base_url(None)
    env_notes = [k for k in ("PDF_AI_LMSTUDIO_URL", "PDF_AI_LMSTUDIO_PORT", "PDF_AI_LMSTUDIO_MODEL") if os.environ.get(k)]
    try:
        req = urllib.request.Request(f"{base_url}/models", method="GET")
        with urllib.request.urlopen(req, timeout=check_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("id", "?") for m in data.get("data", [])]
        if models:
            extra = f" (env: {', '.join(env_notes)})" if env_notes else ""
            return OK, "LM Studio", f"{base_url} | modeller: {', '.join(models[:3])}{extra}"
        return WARN, "LM Studio", f"{base_url} yanit verdi ama yuklu model yok"
    except Exception:
        return WARN, "LM Studio", (
            f"{base_url} erisilemiyor; Opus-MT yedek motoru kullanilir"
            + (f" (env: {', '.join(env_notes)})" if env_notes else "")
        )


def check_translation_cache(cache_path: str = None) -> CheckResult:
    cache_path = cache_path or build_dir("translation_cache.json")
    if not os.path.exists(cache_path):
        return OK, "Ceviri onbellegi", "bos (ilk ceviriler olusturacak)"
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return WARN, "Ceviri onbellegi", "bozuk bicim; ilk calistirmada sifirlanir"
        import re
        contaminated = sum(
            1 for v in data.values() if isinstance(v, str) and re.search(r"(?:CODE_|MTH_)\d+", v)
        )
        return OK, "Ceviri onbellegi", f"{max(0, len(data) - 1)} ceviri hazir, {contaminated} kirli kayit"
    except Exception as exc:
        return WARN, "Ceviri onbellegi", f"okunamadi: {exc}"


def check_leftover_checkpoints(ckpt_dir: str = None) -> CheckResult:
    ckpt_dir = ckpt_dir or build_dir("checkpoints")
    if not os.path.isdir(ckpt_dir):
        return OK, "Checkpoint klasoru", "temiz"
    files = [f for f in os.listdir(ckpt_dir) if f.endswith(".jsonl")]
    if not files:
        return OK, "Checkpoint klasoru", "temiz"
    return OK, "Checkpoint klasoru", (
        f"{len(files)} yarim is dosyasi (resume ile devam eder; --fresh ile sifirlanir)"
    )


def default_checks() -> List[Callable[[], CheckResult]]:
    checks = [check_python]
    checks += [(_make_module_check(n, critical=n in CORE_MODULES)) for n in CORE_MODULES + AI_MODULES + AUX_MODULES]
    checks += [check_tesseract, check_turkish_font, check_lmstudio, check_translation_cache, check_leftover_checkpoints]
    return checks


def _make_module_check(name: str, critical: bool) -> Callable[[], CheckResult]:
    def run() -> CheckResult:
        status, label, detail = check_import(name)
        if status == FAIL and not critical:
            status = WARN
        return status, label, detail
    return run


def run_doctor(checks: List[Callable[[], CheckResult]] = None, print_fn=print) -> int:
    print_fn("==================== PDF AI ENGINE - ORTAM TESHISI ====================")
    results: List[CheckResult] = [c() for c in (checks if checks is not None else default_checks())]
    for status, label, detail in results:
        print_fn(f"  [{status:^5}] {label:22} : {detail}")
    fails = sum(1 for s, _, _ in results if s == FAIL)
    warns = sum(1 for s, _, _ in results if s == WARN)
    print_fn("=======================================================================")
    print_fn(f"  SONUC: {fails} hata, {warns} uyari")
    if fails:
        print_fn("  Hatalar giderilmeden ceviri baslatilamaz (yukaridaki satirlara bakin).")
    elif warns:
        print_fn("  Uyarilarla devam edilebilir; eksik ozellikler yedek mekanizmalara duser.")
    else:
        print_fn("  Tum bilesenler hazir.")
    return 1 if fails else 0
