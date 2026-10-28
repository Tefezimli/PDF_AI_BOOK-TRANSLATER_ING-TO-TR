"""Kalıcı çıktıların (checkpoint/önbellek/ayarlar) tek kökü.

CWD'den bağımsızlık için tüm build/ altı yollar bu modülden türetilir:
varsayılan kök proje dizini altındaki build/'dir — farklı bir dizinden
başlatılan GUI/CLI aynı önbelleği/checkpoint'i görür ve salt-okunur
CWD'de patlamaz. PDF_AI_WORKDIR env'i kökü tamamen başka bir dizine
taşır (testler ve taşınabilir kurulumlar için).

(Not: pip install -e . ile kurulumda bu, repo köküdür.)
Değerler import anında çözülür — testlerde env'i set edip modülü
reload edin ya da fonksiyonlara açık yol geçin.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_path(*parts: str) -> str:
    """Kalıcı çıktı yollarının tek çözüm noktası.

    Öncelik: PDF_AI_WORKDIR env'i; yoksa PROJECT_ROOT/build (CWD'den
    bağımsız). Parça verilmezse kökün kendisini döndürür (makedirs için).
    """
    root = os.environ.get("PDF_AI_WORKDIR")
    if not root:
        root = os.path.join(PROJECT_ROOT, "build")
    return os.path.join(root, *parts) if parts else root


def build_dir(*parts: str) -> str:
    """Eski ad, geriye dönük uyumluluk için duruyor.

    PDF_AI_WORKDIR ayarlıyken build_path ile aynı kökü kullanır; ama
    varsayılanı CWD-göreli 'build/'dir. Yeni kod build_path kullanmalı.
    """
    root = os.environ.get("PDF_AI_WORKDIR")
    if not root:
        root = os.path.join("build")
    return os.path.join(root, *parts) if parts else root
