@echo off
title Wsool STT — Build Executables
cd /d "%~dp0"

echo ============================================
echo   Wsool STT — Build .exe files
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Create clean build venv
if exist build_venv rmdir /s /q build_venv
echo [1/6] Creating clean build environment...
python -m venv build_venv
call build_venv\Scripts\activate.bat

:: Install runtime deps (ONNX, no torch)
echo [2/6] Installing runtime dependencies...
pip install -r requirements.txt --quiet

:: Install build tools
echo [3/6] Installing build tools...
pip install pyinstaller>=6.0 customtkinter>=5.2.0 --quiet

:: Build main app
echo [4/6] Building WsoolSTT.exe...
pyinstaller WsoolSTT.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Main app build failed!
    pause
    exit /b 1
)

:: Build installer
echo [5/6] Building WsoolSTT-Setup.exe...
pyinstaller WsoolSTT-Setup.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Installer build failed!
    pause
    exit /b 1
)

:: Copy .env.example to dist
echo [6/6] Copying config files...
copy .env.example dist\WsoolSTT\.env.example >nul 2>&1
copy run_silent.vbs dist\WsoolSTT\ >nul 2>&1
copy startup.bat dist\WsoolSTT\ >nul 2>&1
copy remove_startup.bat dist\WsoolSTT\ >nul 2>&1

:: Cleanup
deactivate
rmdir /s /q build_venv >nul 2>&1

echo.
echo ============================================
echo   Build complete!
echo.
echo   dist\WsoolSTT\WsoolSTT.exe       — Main app
echo   dist\WsoolSTT-Setup\WsoolSTT-Setup.exe — Installer
echo.
echo   Next: test on a clean Windows machine
echo   without Python installed.
echo ============================================
pause
