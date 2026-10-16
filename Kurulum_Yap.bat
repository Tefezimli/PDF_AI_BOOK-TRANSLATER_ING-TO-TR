@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title PDF AI Book Translator - Akilli Kurulum Sihirbazi
color 0B

:: Yonetici olarak calistirilsa bile proje klasorune sabitlen!
cd /d "%~dp0"

echo ============================================================================
echo        PDF AI BOOK TRANSLATOR (EN -^> TR) - AKILLI KURULUM SIHIRBAZI
echo ============================================================================
echo Calisma Dizini: "%CD%"
echo.

set "PYTHON_EXE="

:: 1. ADIM: Python Launcher (py -3) Kontrolu (En guvenilir yontem)
py -3 -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
    goto :PYTHON_BULUNDU
)

:: 2. ADIM: PATH uzerindeki "python" kontrolu (Microsoft Store sahte exe'sini eler!)
python -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
    goto :PYTHON_BULUNDU
)

:: 3. ADIM: Windows Kayit Defteri (Registry) uzerinden tum Python kurulumlarini tara
for %%R in (HKCU HKLM) do (
    for %%W in ("" "\Wow6432Node") do (
        for /f "tokens=*" %%K in ('reg query "%%R\Software%%~W\Python\PythonCore" 2^>nul') do (
            for /f "tokens=2*" %%A in ('reg query "%%K\InstallPath" /ve 2^>nul ^| findstr "REG_"') do (
                if exist "%%B\python.exe" (
                    "%%B\python.exe" -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>&1
                    if !errorlevel! equ 0 (
                        set "PYTHON_EXE=%%B\python.exe"
                        goto :PYTHON_BULUNDU
                    )
                )
            )
        )
    )
)

:: 4. ADIM: Tum yaygin klasorleri (AppData, Program Files, Conda, C:\Python*) tara
for %%D in (
    "%LocalAppData%\Programs\Python"
    "%ProgramFiles%\Python*"
    "%ProgramFiles(x86)%\Python*"
    "%UserProfile%\anaconda3"
    "%UserProfile%\miniconda3"
    "C:\Python*"
    "D:\Python*"
) do (
    for /d %%P in (%%D) do (
        if exist "%%P\python.exe" (
            "%%P\python.exe" -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYTHON_EXE=%%P\python.exe"
                goto :PYTHON_BULUNDU
            )
        )
        for /d %%S in ("%%P\Python*") do (
            if exist "%%S\python.exe" (
                "%%S\python.exe" -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>&1
                if !errorlevel! equ 0 (
                    set "PYTHON_EXE=%%S\python.exe"
                    goto :PYTHON_BULUNDU
                )
            )
        )
    )
)

:: 5. ADIM: Eger gercekten Python yoksa Winget ile otomatik kurmayi teklif et
color 0E
echo [UYARI] Bilgisayarda gecerli bir Python (3.9+) kurulumu bulunamadi!
echo.
where winget >nul 2>&1
if !errorlevel! equ 0 (
    echo Python 3.11 simdi otomatik olarak indirilsin ve kurulsun mu?
    set /p "INSTALL_PY=Otomatik kurulum icin E yazip Enter'a basin (Iptal icin H): "
    if /i "!INSTALL_PY!"=="E" (
        echo [OTOMATIK KURULUM] Python 3.11 winget ile kuruluyor, lutfen bekleyin...
        winget install -e --id Python.Python.3.11 --scope machine --accept-package-agreements --accept-source-agreements
        if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
        if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
        if defined PYTHON_EXE goto :PYTHON_BULUNDU
    )
)

color 0C
echo.
echo [HATA] Python bulunamadi! Lutfen https://www.python.org/downloads/ adresinden
echo Python 3.11 indirip kurarken en alttaki "Add python.exe to PATH" kutusunu isaretleyin.
pause
exit /b 1

:PYTHON_BULUNDU
echo [OK] Python bulundu: "!PYTHON_EXE!"
"!PYTHON_EXE!" --version
echo.

:: 6. ADIM: Bozuk veya baska bilgisayardan kalma sanal ortami (ai_env) denetle
if exist "ai_env\Scripts\python.exe" (
    "ai_env\Scripts\python.exe" -c "import sys" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ONARIM] Mevcut ai_env baska bir bilgisayardan kopyalanmis veya bozuk. Yenileniyor...
        rmdir /s /q ai_env
    )
)

if not exist "ai_env\Scripts\python.exe" (
    echo [1/5] Sanal ortam ^(ai_env^) olusturuluyor...
    "!PYTHON_EXE!" -m venv ai_env
    if !errorlevel! neq 0 (
        color 0C
        echo [HATA] Sanal ortam olusturulamadi!
        pause
        exit /b 1
    )
) else (
    echo [1/5] Sanal ortam ^(ai_env^) hazir.
)

set "VENV_PY=%CD%\ai_env\Scripts\python.exe"

:: 7. ADIM: Pip ve PyTorch Kurulumu (Once GPU cu128 dener, basarisiz olursa standart surumu kurar)
echo.
echo [2/5] Pip guncelleniyor ve PyTorch kuruluyor...
"!VENV_PY!" -m pip install --upgrade pip
"!VENV_PY!" -m pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128
if !errorlevel! neq 0 (
    echo [BILGI] Nightly cu128 yerine kararli PyTorch surumu kuruluyor...
    "!VENV_PY!" -m pip install torch torchvision
)

:: 8. ADIM: Gerekli Kutuphanelerin Kurulumu
echo.
echo [3/5] Gerekli Python kutuphaneleri kuruluyor...
"!VENV_PY!" -m pip install -r requirements.txt

:: 9. ADIM: Tesseract OCR Kontrolu ve Otomatik Kurulumu
echo.
echo [4/5] Tesseract OCR motoru kontrol ediliyor...
set "TESS_OK=0"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS_OK=1"
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESS_OK=1"
if exist "%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe" set "TESS_OK=1"
where tesseract >nul 2>&1
if !errorlevel! equ 0 set "TESS_OK=1"

if "!TESS_OK!"=="0" (
    echo [BILGI] Tesseract OCR bulunamadi. Winget ile otomatik kuruluyor...
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        winget install -e --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
    ) else (
        echo [UYARI] Slayt/Resim OCR ozelligi icin Tesseract OCR gereklidir:
        echo         https://github.com/UB-Mannheim/tesseract/wiki
    )
) else (
    echo -^> Tesseract OCR hazir.
)

:: 10. ADIM: Ceviri Modelini Yerel Diske Indirme
echo.
echo [5/5] Yapay Zeka Ceviri Modeli ^(Helsinki-NLP/opus-mt-tc-big-en-tr^) yerel diske indiriliyor...
"!VENV_PY!" -c "import os; os.environ['HF_HUB_OFFLINE']='0'; os.environ['TRANSFORMERS_OFFLINE']='0'; from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; m='Helsinki-NLP/opus-mt-tc-big-en-tr'; AutoTokenizer.from_pretrained(m); AutoModelForSeq2SeqLM.from_pretrained(m); print('-> Model yerel diske basariyla kaydedildi!')"

:: 11. ADIM: C++ AiEngine Derleme Kontrolu (Opsiyonel)
where cmake >nul 2>&1
if !errorlevel! equ 0 (
    if exist "CMakeLists.txt" (
        echo.
        echo [EKSTRA] C++ OpenMP Motoru derleniyor...
        if not exist "build" mkdir build
        cd build
        cmake .. >nul 2>&1
        cmake --build . --config Release >nul 2>&1
        if exist "Release\AiEngine.exe" copy /Y "Release\AiEngine.exe" "AiEngine.exe" >nul
        cd ..
    )
)

color 0A
echo.
echo ============================================================================
echo [BASARILI] Kurulum eksiksiz tamamlandi!
echo Artik internetiniz kapali olsa bile "Baslat.bat" ile arayuzu acabilirsiniz.
echo ============================================================================
pause