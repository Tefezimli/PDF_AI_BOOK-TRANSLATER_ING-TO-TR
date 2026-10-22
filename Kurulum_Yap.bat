@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title PDF AI Book Translator - Akıllı Kurulum Sihirbazı
color 0B

:: 1. Yönetici olarak veya system32'de çalıştırılsa bile KESİNLİKLE proje klasörüne kilitlen
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo ============================================================================
echo        PDF AI BOOK TRANSLATOR (EN -^> TR) - EVRENSEL KURULUM SIHIRBAZI
echo ============================================================================
echo [ÖNEMLİ BİLGİLENDİRME]
echo   * İLK KURULUMDA yapay zeka modelinin (~1.2 GB) ve gerekli kütüphanelerin
echo     yerel diske indirilebilmesi için AKTİF İNTERNET BAĞLANTISI GEREKİR.
echo   * Kurulum bir kez tamamlandıktan sonra program %%100 ÇEVRİMDIŞI (Air-Gapped)
echo     olarak internete hiç bağlanmadan sonsuza kadar çalışacaktır!
echo ============================================================================
echo Proje Klasörü: "%PROJECT_DIR%"
echo.

:: ----------------------------------------------------------------------------
:: 0. ADIM: İnternet Bağlantısı Kontrolü
:: ----------------------------------------------------------------------------
echo [0/6] İnternet erişimi kontrol ediliyor...
ping -n 1 huggingface.co >nul 2>&1
if !errorlevel! neq 0 (
    ping -n 1 8.8.8.8 >nul 2>&1
    if !errorlevel! neq 0 (
        color 0E
        echo.
        echo ----------------------------------------------------------------------------
        echo [DİKKAT: İNTERNET BAĞLANTISI BULUNAMADI!]
        echo İlk kurulum aşamasında yapay zeka çeviri modeli ve Python paketleri
        echo indirileceği için lütfen bilgisayarınızın internet bağlantısını açın.
        echo ----------------------------------------------------------------------------
        echo.
        pause
    ) else (
        echo -> İnternet bağlantısı aktif.
    )
) else (
    echo -> İnternet bağlantısı aktif.
)
echo.

set "PYTHON_EXE="

:: ----------------------------------------------------------------------------
:: 1. ADIM: Python Yorumlayıcısını Tespit Et (3.10 - 3.12)
:: ----------------------------------------------------------------------------
echo [1/6] Python yorumlayıcısı taranıyor...

:: 1.1 Python Launcher (py -3)
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
    goto :PYTHON_BULUNDU
)

:: 1.2 PATH üzerindeki python (3.10+)
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
    goto :PYTHON_BULUNDU
)

:: 1.3 Windows Kayıt Defteri (Registry) Taraması (Python 3.10, 3.11, 3.12)
for %%R in (HKCU HKLM) do (
    for %%W in ("" "\Wow6432Node") do (
        for /f "tokens=*" %%K in ('reg query "%%R\Software%%~W\Python\PythonCore" 2^>nul') do (
            for /f "tokens=2*" %%A in ('reg query "%%K\InstallPath" /ve 2^>nul ^| findstr "REG_"') do (
                if exist "%%B\python.exe" (
                    "%%B\python.exe" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
                    if !errorlevel! equ 0 (
                        set "PYTHON_EXE=%%B\python.exe"
                        goto :PYTHON_BULUNDU
                    )
                )
            )
        )
    )
)

:: 1.4 Standart Klasör Taraması (Python 3.10+)
for %%D in (
    "%LocalAppData%\Programs\Python\Python312"
    "%LocalAppData%\Programs\Python\Python311"
    "%LocalAppData%\Programs\Python\Python310"
    "%ProgramFiles%\Python312"
    "%ProgramFiles%\Python311"
    "%ProgramFiles%\Python310"
    "C:\Python312"
    "C:\Python311"
    "C:\Python310"
) do (
    if exist "%%~D\python.exe" (
        "%%~D\python.exe" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=%%~D\python.exe"
            goto :PYTHON_BULUNDU
        )
    )
)

:: 1.5 Eğer sistemde sadece Python 3.9 veya altı varsa ya da hiç yoksa Winget ile kur
color 0E
echo [UYARI] Sistemde modern yapay zeka kütüphaneleriyle uyumlu Python (3.10+) bulunamadı.
echo -> (Not: Eski Python 3.9 sürümleri PyMuPDF/Surya-OCR/Torch ile kütüphane çakışması yaratır).
echo -> Python 3.11 Winget üzerinden otomatik kuruluyor, lütfen bekleyin...
echo.

where winget >nul 2>&1
if !errorlevel! equ 0 (
    winget install -e --id Python.Python.3.11 --scope machine --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    if defined PYTHON_EXE goto :PYTHON_BULUNDU

    winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    if defined PYTHON_EXE goto :PYTHON_BULUNDU
)

color 0C
echo.
echo ============================================================================
echo [HATA] Python 3.10+ otomatik kurulamadı!
echo Lütfen https://www.python.org/downloads/ adresinden Python 3.11 indirip kurun.
echo Kurulum esnasında en alttaki "Add python.exe to PATH" seçeneğini İŞARETLEYİN!
echo ============================================================================
pause
exit /b 1

:PYTHON_BULUNDU
echo -> Python bulundu: "!PYTHON_EXE!"
"!PYTHON_EXE!" --version
echo.

:: ----------------------------------------------------------------------------
:: 2. ADIM: Sanal Ortamın (ai_env) Oluşturulması ve Onarımı
:: ----------------------------------------------------------------------------
echo [2/6] Sanal ortam ^(ai_env^) hazırlanıyor...
set "VENV_DIR=%PROJECT_DIR%\ai_env"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if exist "!VENV_PY!" (
    "!VENV_PY!" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ONARIM] Mevcut sanal ortam başka bir bilgisayardan kopyalanmış veya eski Python sürümüne ait.
        echo -> Sanal ortam sıfırlanıp yeniden inşa ediliyor...
        rmdir /s /q "!VENV_DIR!"
    )
)

if not exist "!VENV_PY!" (
    echo -> Yeni sanal ortam oluşturuluyor: "!VENV_DIR!"
    "!PYTHON_EXE!" -m venv "!VENV_DIR!"
    if !errorlevel! neq 0 (
        color 0C
        echo [HATA] Sanal ortam oluşturulamadı!
        pause
        exit /b 1
    )
)
echo -> Sanal ortam hazır.
echo.

:: ----------------------------------------------------------------------------
:: 3. ADIM: Pip, Setuptools, Wheel ve PyTorch Yapılandırması
:: ----------------------------------------------------------------------------
echo [3/6] Pip güncelleniyor ve PyTorch (GPU / CPU) kuruluyor...
"!VENV_PY!" -m pip install --upgrade pip setuptools wheel

:: NVIDIA GPU Varlığını Çift Yöntemle (nvidia-smi + Windows Donanım Kayıt Defteri) Tara
set "HAS_NVIDIA=0"
where nvidia-smi >nul 2>&1
if !errorlevel! equ 0 set "HAS_NVIDIA=1"
if "!HAS_NVIDIA!"=="0" (
    reg query "HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}" /s 2>nul | findstr /i "NVIDIA" >nul 2>&1
    if !errorlevel! equ 0 set "HAS_NVIDIA=1"
)

set "TORCH_OK=0"
if "!HAS_NVIDIA!"=="1" (
    echo -> NVIDIA Ekran Kartı tespit edildi. CUDA hızlandırmalı PyTorch yapılandırılıyor...
    
    echo -> [1/3] Blackwell (RTX 50xx / cu128 nightly) deneniyor...
    "!VENV_PY!" -m pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128
    "!VENV_PY!" -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
    if !errorlevel! equ 0 (
        set "TORCH_OK=1"
        echo -> CUDA 12.8 nightly başarıyla kuruldu ve doğrulandı.
    )

    if "!TORCH_OK!"=="0" (
        echo -> [2/3] Kararlı CUDA 12.4 (RTX 30xx / 40xx) kuruluyor...
        "!VENV_PY!" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
        "!VENV_PY!" -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
        if !errorlevel! equ 0 (
            set "TORCH_OK=1"
            echo -> CUDA 12.4 başarıyla kuruldu ve doğrulandı.
        )
    )

    if "!TORCH_OK!"=="0" (
        echo -> [3/3] Kararlı CUDA 12.1 kuruluyor...
        "!VENV_PY!" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
        "!VENV_PY!" -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
        if !errorlevel! equ 0 (
            set "TORCH_OK=1"
            echo -> CUDA 12.1 başarıyla kuruldu ve doğrulandı.
        )
    )
)

if "!TORCH_OK!"=="0" (
    echo -> Standart kararlı PyTorch (CPU) kuruluyor...
    "!VENV_PY!" -m pip install torch torchvision
)
echo.

:: ----------------------------------------------------------------------------
:: 4. ADIM: Tüm Proje Kütüphanelerinin Hiyerarşik ve Garantili Kurulumu
:: ----------------------------------------------------------------------------
echo [4/6] NLP, PDF, OCR ve Derin Öğrenme kütüphaneleri kuruluyor...

echo -> [Grup 1] Çekirdek NLP ve Çeviri Bağımlılıkları (transformers, sacremoses, sentencepiece)...
"!VENV_PY!" -m pip install transformers>=4.40.0 sentencepiece sacremoses accelerate huggingface_hub safetensors requests tqdm

echo -> [Grup 2] PDF ve Görsel İşleme Motorları (pymupdf, pillow, opencv-python, pytesseract)...
"!VENV_PY!" -m pip install pymupdf>=1.24.0 pillow>=10.0.0 opencv-python>=4.8.0 pytesseract>=0.3.10 numpy>=1.24.0 pypdfium2

echo -> [Grup 3] Opsiyonel Derin Öğrenme OCR Paketleri (surya-ocr, ultralytics)...
"!VENV_PY!" -m pip install surya-ocr ultralytics >nul 2>&1
echo.

:: ----------------------------------------------------------------------------
:: 5. ADIM: Tesseract OCR Motoru ve Türkçe/İngilizce Dil Verileri
:: ----------------------------------------------------------------------------
echo [5/6] Tesseract OCR motoru denetleniyor...
set "TESS_DIR="
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files\Tesseract-OCR"
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files (x86)\Tesseract-OCR"
if exist "%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe" set "TESS_DIR=%LocalAppData%\Programs\Tesseract-OCR"

if not defined TESS_DIR (
    where tesseract >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%t in ('where tesseract') do set "TESS_DIR=%%~dpt"
    )
)

if not defined TESS_DIR (
    echo -> Tesseract OCR bulunamadı. Winget ile kuruluyor...
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        winget install -e --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
        if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files\Tesseract-OCR"
        if exist "%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe" set "TESS_DIR=%LocalAppData%\Programs\Tesseract-OCR"
    )
)

if defined TESS_DIR (
    echo -> Tesseract OCR hazır: "!TESS_DIR!"
    if exist "!TESS_DIR!\tessdata" (
        if not exist "!TESS_DIR!\tessdata\tur.traineddata" (
            echo -> Türkçe OCR dil paketi (tur.traineddata) indiriliyor...
            "!VENV_PY!" -c "import urllib.request, os; p=r'!TESS_DIR!\tessdata\tur.traineddata'; urllib.request.urlretrieve('https://github.com/tesseract-ocr/tessdata_fast/raw/main/tur.traineddata', p) if not os.path.exists(p) else None" >nul 2>&1
        )
        if not exist "!TESS_DIR!\tessdata\eng.traineddata" (
            echo -> İngilizce OCR dil paketi (eng.traineddata) indiriliyor...
            "!VENV_PY!" -c "import urllib.request, os; p=r'!TESS_DIR!\tessdata\eng.traineddata'; urllib.request.urlretrieve('https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata', p) if not os.path.exists(p) else None" >nul 2>&1
        )
    )
)
echo.

:: ----------------------------------------------------------------------------
:: 6. ADIM: Çeviri Modelinin İndirilmesi ve %100 Çevrimdışı Kilit Doğrulaması
:: ----------------------------------------------------------------------------
echo [6/6] Yapay Zeka Çeviri Modeli (Helsinki-NLP/opus-mt-tc-big-en-tr) indiriliyor...
echo -> Model ağırlıkları HuggingFace üzerinden yerel önbelleğe alınıyor...

"!VENV_PY!" -c "import os; os.environ['HF_HUB_OFFLINE']='0'; os.environ['TRANSFORMERS_OFFLINE']='0'; from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; m='Helsinki-NLP/opus-mt-tc-big-en-tr'; print('-> Tokenizer indiriliyor...'); AutoTokenizer.from_pretrained(m); print('-> Model ağırlıkları indiriliyor (~1.2 GB)...'); AutoModelForSeq2SeqLM.from_pretrained(m); print('[OK] Model başarıyla yerel diske kaydedildi.')"

if !errorlevel! neq 0 (
    echo [UYARI] Ağ kesintisi nedeniyle model indirme 2. kez deneniyor...
    "!VENV_PY!" -c "import os; os.environ['HF_HUB_OFFLINE']='0'; os.environ['TRANSFORMERS_OFFLINE']='0'; from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; m='Helsinki-NLP/opus-mt-tc-big-en-tr'; AutoTokenizer.from_pretrained(m); AutoModelForSeq2SeqLM.from_pretrained(m); print('[OK] Model 2. denemede kaydedildi.')"
)

:: Modelin %100 Çevrimdışı (Air-Gapped) Çalıştığını Kesin Olarak Test Et
echo -> Çevrimdışı (internetsiz) çalışma testi yapılıyor...
"!VENV_PY!" -c "import os; os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'; from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; m='Helsinki-NLP/opus-mt-tc-big-en-tr'; tok=AutoTokenizer.from_pretrained(m, local_files_only=True); mod=AutoModelForSeq2SeqLM.from_pretrained(m, local_files_only=True); print('-> %100 ÇEVRİMDIŞI KİLİT ONAYLANDI: Model internetsiz çalışmaya hazır.')"

if !errorlevel! neq 0 (
    color 0C
    echo.
    echo [KRİTİK HATA] Model çevrimdışı yüklenemedi!
    echo Lütfen aktif bir internet bağlantısıyla Kurulum_Yap.bat dosyasını tekrar çalıştırın.
    pause
    exit /b 1
)

:: ----------------------------------------------------------------------------
:: EKSTRA: C++ AiEngine Derleme Kontrolü (Opsiyonel)
:: ----------------------------------------------------------------------------
where cmake >nul 2>&1
if !errorlevel! equ 0 (
    if exist "CMakeLists.txt" (
        echo.
        echo [EKSTRA] C++ OpenMP Motoru kontrol ediliyor / derleniyor...
        if not exist "build" mkdir build
        cd build
        cmake .. >nul 2>&1
        cmake --build . --config Release >nul 2>&1
        if exist "Release\AiEngine.exe" copy /Y "Release\AiEngine.exe" "AiEngine.exe" >nul
        cd "%PROJECT_DIR%"
    )
)

:: ----------------------------------------------------------------------------
:: NİHAİ TEST VE SİSTEM SAĞLIK RAPORU
:: ----------------------------------------------------------------------------
echo.
echo ============================================================================
echo                    SİSTEM KURULUM VE SAĞLIK RAPORU
echo ============================================================================
"!VENV_PY!" -c "import sys, fitz, PIL, cv2, torch, transformers; print(f'  [+] Python        : {sys.version.split()[0]}'); print(f'  [+] PyMuPDF (fitz): {fitz.__version__}'); print(f'  [+] OpenCV        : {cv2.__version__}'); print(f'  [+] Pillow (PIL)  : {PIL.__version__}'); print(f'  [+] Transformers  : {transformers.__version__}'); dev = ('CUDA: ' + torch.cuda.get_device_name(0)) if torch.cuda.is_available() else 'CPU (Stabil Standart Mod)'; print(f'  [+] Donanım/Aygıt : {dev}')"

color 0A
echo ============================================================================
echo [BAŞARILI] Kurulum eksiksiz tamamlandı!
echo Artık internet bağlantınız kapalı olsa bile "Baslat.bat" ile programı
echo güvenle ve %100 çevrimdışı çalıştırabilirsiniz.
echo ============================================================================
pause
