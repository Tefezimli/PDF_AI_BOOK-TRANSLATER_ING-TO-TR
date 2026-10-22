@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title PDF AI Book Translator - Çalışma Konsolu
color 0B

:: 1. Yönetici olarak veya system32'de çalıştırılsa bile KESİNLİKLE proje klasörüne kilitlen
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo ============================================================================
echo        PDF AI BOOK TRANSLATOR (EN -^> TR) - ÇALIŞMA KONSOLU
echo ============================================================================
echo Proje Klasörü: "%PROJECT_DIR%"
echo.

:: 2. Tesseract OCR Yolunu ve TESSDATA_PREFIX Değişkenini Ortama Tanımla
if exist "C:\Program Files\Tesseract-OCR" (
    set "PATH=C:\Program Files\Tesseract-OCR;!PATH!"
    if exist "C:\Program Files\Tesseract-OCR\tessdata" (
        set "TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata"
    )
)
if exist "%LocalAppData%\Programs\Tesseract-OCR" (
    set "PATH=%LocalAppData%\Programs\Tesseract-OCR;!PATH!"
    if exist "%LocalAppData%\Programs\Tesseract-OCR\tessdata" (
        set "TESSDATA_PREFIX=%LocalAppData%\Programs\Tesseract-OCR\tessdata"
    )
)

:: 3. Sanal Ortam (ai_env) Varlık Kontrolü
set "VENV_DIR=%PROJECT_DIR%\ai_env"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "!VENV_PY!" (
    color 0E
    echo ----------------------------------------------------------------------------
    echo [İLK ÇALIŞTIRMA BİLGİLENDİRMESİ]
    echo Sanal ortam (ai_env) henüz kurulmamış.
    echo DİKKAT: İlk kurulumda yapay zeka modelinin (~1.2 GB) ve paketlerin
    echo indirilebilmesi için İNTERNET BAĞLANTISI GEREKLİDİR.
    echo Kurulum bittikten sonra program tamamen ÇEVRİMDIŞI (internetsiz) çalışacaktır!
    echo ----------------------------------------------------------------------------
    echo -> Kurulum sihirbazı başlatılıyor...
    echo.
    call Kurulum_Yap.bat
    if !errorlevel! neq 0 (
        color 0C
        echo [HATA] Kurulum tamamlanamadı. Lütfen internet bağlantınızı kontrol edip tekrar deneyin.
        pause
        exit /b 1
    )
)

:: 4. Sanal Ortam Taşınabilirlik ve Python Sürüm Uyumluluğu Testi
"!VENV_PY!" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if !errorlevel! neq 0 (
    color 0E
    echo [ONARIM] Sanal ortam başka bir bilgisayardan taşınmış veya Python sürümü uyumsuz.
    echo -> DİKKAT: Onarım ve paket indirmesi için İNTERNET BAĞLANTISI GEREKİR.
    echo -> Sanal ortam otomatik olarak onarılıyor...
    echo.
    rmdir /s /q "!VENV_DIR!"
    call Kurulum_Yap.bat
    if !errorlevel! neq 0 (
        color 0C
        echo [HATA] Sanal ortam onarılamadı.
        pause
        exit /b 1
    )
)

:: 5. Kütüphaneler ve Çevrimdışı Yapay Zeka Modelinin Hazırlık Denetimi
echo [KONTROL] Sistem kütüphaneleri ve çevrimdışı yapay zeka modeli denetleniyor...
"!VENV_PY!" -c "import fitz, PIL, cv2, torch, transformers; from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; m='Helsinki-NLP/opus-mt-tc-big-en-tr'; AutoTokenizer.from_pretrained(m, local_files_only=True); AutoModelForSeq2SeqLM.from_pretrained(m, local_files_only=True)" >nul 2>&1
if !errorlevel! neq 0 (
    color 0E
    echo.
    echo ----------------------------------------------------------------------------
    echo [UYARI: YAPAY ZEKA MODELİ VEYA KÜTÜPHANELER EKSİK!]
    echo Çeviri modelinin HuggingFace üzerinden ilk defa indirilmesi için
    echo İNTERNET BAĞLANTISI GEREKLİDİR (~1.2 GB model indirilecek).
    echo Model bir kez indikten sonra çeviriler %%100 ÇEVRİMDIŞI yapılacaktır.
    echo ----------------------------------------------------------------------------
    echo -> Eksik bileşenleri indirmek için kurulum sihirbazı başlatılıyor...
    echo.
    call Kurulum_Yap.bat
    if !errorlevel! neq 0 (
        color 0C
        echo [HATA] Model veya kütüphaneler indirilemedi.
        pause
        exit /b 1
    )
)

:: 6. Donanım Bilgisini Oku ve Uygulamayı Başlat
echo -> Sistem hazır. Aktif donanım tespiti yapılıyor...
for /f "delims=" %%D in ('"!VENV_PY!" -c "import torch; print(('GPU: ' + torch.cuda.get_device_name(0)) if torch.cuda.is_available() else 'CPU Hızlandırma Modu (Stabil)')"') do set "ACTIVE_DEVICE=%%D"
echo -> Aktif Hesaplama Motoru: !ACTIVE_DEVICE!
echo.

color 0A
if exist "app_gui.py" (
    echo [SİSTEM] Grafik Kullanıcı Arayüzü ^(GUI^) başlatılıyor...
    "!VENV_PY!" app_gui.py
) else (
    echo [SİSTEM] Komut satırı motoru ^(CLI^) başlatılıyor...
    "!VENV_PY!" pdf_bridge.py
)

if !errorlevel! neq 0 (
    color 0C
    echo.
    echo ============================================================================
    echo [HATA] Uygulama beklenmeyen bir hatayla kapandı.
    echo ============================================================================
    pause
)
