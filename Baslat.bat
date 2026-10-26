@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PDF AI Engine Pro - Çeviri İstasyonu

echo ============================================================================
echo      PDF AI ENGINE PRO - QWEN 2.5 14B & HİBRİT ÇEVİRİ İSTASYONU
echo ============================================================================
echo [SİSTEM] Çalışma ortamı doğrulanıyor...

set "PYTHON_CMD="

if exist "ai_env\Scripts\python.exe" (
    set "PYTHON_CMD=ai_env\Scripts\python.exe"
) else if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [HATA] Python yorumlayıcısı bulunamadı! Lütfen önce Kurulum_Yap.bat çalıştırın.
    pause
    exit /b 1
)

echo [SİSTEM] Başlatılıyor: %PYTHON_CMD% app_gui.py
"%PYTHON_CMD%" app_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [HATA] Uygulama beklenmedik bir hatayla kapandı.
    pause
)
