@echo off
:: Adds Voice-to-Text to Windows Startup
:: Run this ONCE to enable auto-start with Windows

set "SCRIPT_DIR=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP%\Voice-to-Text.lnk"

:: Create shortcut using PowerShell
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT_DIR%run_silent.vbs'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Voice-to-Text Dictation'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [OK] Voice-to-Text added to Windows Startup!
    echo     Location: %SHORTCUT%
    echo     It will start automatically next time you log in.
) else (
    echo [ERROR] Failed to create startup shortcut.
)
pause
