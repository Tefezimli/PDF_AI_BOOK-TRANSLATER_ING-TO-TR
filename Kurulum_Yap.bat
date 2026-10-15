@echo off
chcp 65001 >nul
title PDF AI Book Translator - Otomatik Kurulum Sihirbazi
color 0B

echo ============================================================================
echo        PDF AI BOOK TRANSLATOR (EN -^> TR) - ILK KURULUM SIHIRBAZI
echo ============================================================================
echo.

:: 1. Python Kontrolu
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [HATA] Sistemde Python bulunamadi! Lutfen Python 3.10+ yukleyin.
    pause
    exit /b
)

:: 2. Sanal Ortam (ai_env) Olusturma
if not exist "ai_env\Scripts\activate.bat" (
    echo [1/5] Sanal ortam ^(ai_env^) olusturuluyor...
    python -m venv ai_env
) else (
    echo [1/5] Sanal ortam ^(ai_env^) zaten mevcut, aktif ediliyor...
)

call ai_env\Scripts\activate.bat

:: 3. Pip ve RTX 5080 (sm_120 / CUDA 12.8) Uyumlu PyTorch Kurulumu
echo.
echo [2/5] Pip guncelleniyor ve PyTorch kuruluyor...
python -m pip install --upgrade pip
pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128
if %errorlevel% neq 0 (
    echo [BILGI] Nightly cu128 paketine erisilemedi, standart kararli PyTorch kuruluyor...
    pip install torch torchvision
)

:: 4. Diger Kutuphanelerin Kurulumu
echo.
echo [3/5] Gerekli Python kutuphaneleri ^(PyMuPDF, Transformers, OpenCV vb.^) kuruluyor...
pip install -r requirements.txt

:: 5. Ceviri Modelini Yerel Diske Indirme (Sonrasinda %100 Offline Calismasi Icin)
echo.
echo [4/5] Helsinki-NLP/opus-mt-tc-big-en-tr modeli yerel önbelleğe indiriliyor...
python -c "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; m='Helsinki-NLP/opus-mt-tc-big-en-tr'; AutoTokenizer.from_pretrained(m); AutoModelForSeq2SeqLM.from_pretrained(m); print('-> Model basariyla yerel diske kaydedildi!')"

:: 6. C++ AiEngine Derleme Kontrolu (CMake varsa otomatik derler)
echo.
echo [5/5] C++ OpenMP Motoru ^(AiEngine^) kontrol ediliyor...
where cmake >nul 2>&1
if %errorlevel% equ 0 (
    if not exist "build" mkdir build
    cd build
    cmake ..
    cmake --build . --config Release
    if exist "Release\AiEngine.exe" copy /Y "Release\AiEngine.exe" "AiEngine.exe" >nul
    cd ..
    echo -^> C++ Motoru basariyla derlendi!
) else (
    echo [BILGI] CMake bulunamadi, C++ derlemesi atlandi ^(Python Auto-Fit motoru aktif^).
)

color 0A
echo.
echo ============================================================================
echo [BASARILI] Kurulum tamamlandi! Artik internetiniz kapali olsa bile
echo "Baslat.bat" dosyasina cift tiklayarak arayuzu acabilirsiniz.
echo ============================================================================
pause