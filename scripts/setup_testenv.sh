#!/usr/bin/env bash
# Tekrarlanabilir hafif test ortamı (torch/transformers gerekmez).
# Kullanim:  ./scripts/setup_testenv.sh [hedef]   (varsayilan: /tmp/pdfai_testenv)
set -e
cd "$(dirname "$0")/.."
TARGET="${1:-/tmp/pdfai_testenv}"

python3 -m venv "$TARGET"
"$TARGET/bin/pip" install --upgrade pip -q
"$TARGET/bin/pip" install pymupdf numpy pillow pytesseract pytest ruff
"$TARGET/bin/pip" install --no-deps -e .   # pdfai-translate komutu (hafif)

echo
echo "Hazir. Dogrulama reçeteleri:"
echo "  $TARGET/bin/python -m pytest        # tum test paketi"
echo "  $TARGET/bin/python -m ruff check .  # lint"
echo "  $TARGET/bin/pdfai-translate --doctor"
echo "  $TARGET/bin/pdfai-translate --eval"
