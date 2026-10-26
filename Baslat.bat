@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PDF AI Engine Pro v18.0

echo ============================================================================
echo                    PDF AI ENGINE PRO - CEVIRI SISTEMI
echo ============================================================================

set "PY_EXE="
if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
) else if exist "C:\Users\efe\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
    set "PY_EXE=C:\Users\efe\AppData\Local\Python\pythoncore-3.14-64\python.exe"
) else if exist "ai_env\Scripts\python.exe" (
    set "PY_EXE=ai_env\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

echo [SISTEM] Aktif Python: %PY_EXE%
echo [SISTEM] Grafik Arayuz baslatiliyor...
echo.

"%PY_EXE%" app_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ============================================================================
    echo [HATA] Uygulama beklenmedik bir sekilde kapandi.
    echo ============================================================================
    pause
)
