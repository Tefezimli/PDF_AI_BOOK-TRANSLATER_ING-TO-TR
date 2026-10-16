@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title PDF AI Book Translator - Calisma Konsolu
cd /d "%~dp0"

if not exist "ai_env\Scripts\python.exe" (
    color 0E
    echo [BILGI] Sanal ortam ^(ai_env^) henuz kurulmamis. Otomatik kurulum baslatiliyor...
    call Kurulum_Yap.bat
)

:: Sanal ortamin bu bilgisayarda calisip calismadigini test et
"ai_env\Scripts\python.exe" -c "import sys" >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo [ONARIM] Sanal ortam baska bir bilgisayardan tasinmis. Bu bilgisayar icin onariliyor...
    rmdir /s /q ai_env
    call Kurulum_Yap.bat
)

if exist "app_gui.py" (
    echo [SISTEM] Grafik Arayuz ^(GUI^) baslatiliyor...
    "ai_env\Scripts\python.exe" app_gui.py
) else (
    echo [SISTEM] Komut satiri motoru baslatiliyor...
    "ai_env\Scripts\python.exe" pdf_bridge.py
)

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [HATA] Uygulama beklenmedik bir hatayla kapandi.
    pause
)