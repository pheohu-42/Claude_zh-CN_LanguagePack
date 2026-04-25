@echo off
chcp 65001 >nul
echo.
echo ========================================
echo  Claude Desktop 中文语言包
echo ========================================
echo.
echo [1] 安装中文语言包
echo [2] 卸载中文语言包
echo [3] 退出
echo.
set /p choice=请选择操作 (1/2/3): 

if "%choice%"=="1" (
    powershell -ExecutionPolicy Bypass -File "%~dp0Claude_zh-CN_LanguagePack.ps1" -Action install
) else if "%choice%"=="2" (
    powershell -ExecutionPolicy Bypass -File "%~dp0Claude_zh-CN_LanguagePack.ps1" -Action uninstall
) else (
    echo 已退出
)

pause
