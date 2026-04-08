@echo off
title Voice-to-Text Installer
cd /d "%~dp0"

echo ============================================
echo   Voice-to-Text — Installation
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
pip install -r requirements.txt

:: Download Silero VAD model (first run cache)
echo [3/3] Pre-downloading VAD model...
python -c "import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True); print('VAD model ready.')"

echo.
echo ============================================
echo   Installation complete!
echo   Edit .env to add your GROQ_API_KEY
echo   Then run: run.bat
echo ============================================
pause
