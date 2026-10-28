#!/usr/bin/env bash
# PDF AI Engine Pro - Linux / macOS Baslatici
# Kullanim:  ./Baslat.sh            (grafik arayuz)
#            ./Baslat.sh --cli      (komut satiri yardimi, bkz. pdf_bridge.py)
set -e
cd "$(dirname "$0")"

# 1. Sanal ortam -> sistem python3 sirasiyla
if [ -x "ai_env/bin/python" ]; then
    PYTHON_CMD="ai_env/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    echo "[HATA] Python 3 bulunamadi!"
    echo "  -> once: python3 -m venv ai_env && ai_env/bin/pip install -r requirements.txt"
    exit 1
fi

# 2. Bagimliliklar kurulu mu? (ilk calistirmada otomatik kurulum onerisi)
if ! "$PYTHON_CMD" -c "import pymupdf, fitz" >/dev/null 2>&1; then
    echo "[BILGI] Bagimliliklar eksik gorunuyor. Oncelikle:"
    echo "  -> $PYTHON_CMD -m pip install -r requirements.txt"
    echo "  -> Tesseract OCR icin: sudo pacman -S tesseract (Arch) / sudo apt install tesseract-ocr (Debian)"
    exit 1
fi

# 3. GUI'yi baslat (--cli ile pdf_bridge komut satiri modu)
if [ "$1" = "--cli" ]; then
    shift
    exec "$PYTHON_CMD" pdf_bridge.py "$@"
fi

echo "[SISTEM] Baslatiliyor: $PYTHON_CMD app_gui.py"
exec "$PYTHON_CMD" app_gui.py
