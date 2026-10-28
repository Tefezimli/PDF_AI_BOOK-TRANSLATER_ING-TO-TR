"""Kalıcı dosyalar için tek kök: PDF_AI_WORKDIR env'i ya da 'build/'.

Önceden tüm yollar CWD-göreliydi; farklı klasörden başlatılan GUI/CLI
aynı önbelleği/checkpoint'i göremiyordu. Artık kök tek yerden çözülür.
Not: değerler import anında çözülür — testlerde env'i set edip modülü
reload edin ya da fonksiyonlara açık yol geçin.
"""
import os


def build_dir(*parts: str) -> str:
    root = os.environ.get("PDF_AI_WORKDIR")
    if not root:
        root = os.path.join("build")
    return os.path.join(root, *parts) if parts else root
