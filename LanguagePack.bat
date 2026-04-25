@echo off
chcp 65001 >nul 2>&1
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/k \"%~f0\"' -Verb RunAs"
    exit /b
)

:menu
cls
echo.
echo   ==================================
echo    Claude Desktop Chinese Language
echo   ==================================
echo.
echo   [1] Install
echo   [2] Uninstall
echo   [3] Extract English (dev)
echo   [4] Exit
echo.
set /p choice=Select (1/2/3/4):

if "%choice%"=="1" (
    echo.
    python "%~dp0install.py" install --auto-restart
    echo.
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    python "%~dp0install.py" uninstall
    echo.
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    python "%~dp0install.py" extract
    echo.
    pause
    goto menu
)
if "%choice%"=="4" exit
goto menu
