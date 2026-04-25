@echo off
chcp 65001 >nul 2>&1
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)
powershell -ExecutionPolicy Bypass -File "%~dp0Claude_zh-CN_一键安装.ps1"
