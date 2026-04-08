@echo off
:: Removes Voice-to-Text from Windows Startup

set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Voice-to-Text.lnk"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [OK] Voice-to-Text removed from Windows Startup.
) else (
    echo [INFO] Voice-to-Text was not in Startup.
)
pause
