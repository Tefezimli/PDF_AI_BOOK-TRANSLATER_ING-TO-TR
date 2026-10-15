@echo off
chcp 65001 >nul
title PDF AI Book Translator - Calisma Konsolu
cd /d "%~dp0"

if not exist "ai_env\Scripts\activate.bat" (
    color 0C
    echo [UYARI] Sanal ortam ^(ai_env^) bulunamadi!
    echo Lutfen once "Kurulum_Yap.bat" dosyasini calistirin.
    pause
    exit /b
)

call ai_env\Scripts\activate.bat

if exist "app_gui.py" (
    echo [SISTEM] Grafik Arayuz ^(GUI^) baslatiliyor...
    python app_gui.py
) else (
    echo [SISTEM] Komut satiri motoru baslatiliyor...
    python pdf_bridge.py
)

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [HATA] Uygulama beklenmedik bir hatayla kapandi.
    pause
)