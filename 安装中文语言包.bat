@echo off
setlocal
set "SCRIPT=%~dp0LanguagePack.ps1"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%SCRIPT%" (
    echo Internal installer script not found.
    pause
    exit /b 1
)
if not exist "%PS_EXE%" set "PS_EXE=powershell.exe"
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
if errorlevel 1 (
    echo.
    echo Installer script failed.
    pause
    exit /b 1
)
endlocal
