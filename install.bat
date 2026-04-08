@echo off
title Wsool STT — Installation
cd /d "%~dp0"

echo ============================================
echo   Wsool STT — Installation
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create venv
echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

:: Install deps
echo [2/3] Installing dependencies...
pip install -r requirements.txt --quiet

:: Verify ONNX model is available
echo [3/3] Verifying VAD model...
python -c "from silero_vad import load_silero_vad; load_silero_vad(onnx=True); print('VAD model ready (ONNX).')"

echo.
echo ============================================
echo   Installation complete!
echo.
echo   Option 1: Run the Setup Wizard:
echo     python installer.py
echo.
echo   Option 2: Edit .env manually then run:
echo     run.bat
echo ============================================
pause
