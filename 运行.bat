@echo off
chcp 65001 >nul
cd /d "%~dp0"
title UPS IBW Processor

:: 若本文件夹内有便携 Python，优先使用
if exist "python\python.exe" (
    "python\python.exe" XPS_UPS.py
    goto :done
)

:: 否则用系统/Anaconda 里的 Python
python --version >nul 2>nul
if errorlevel 1 (
    echo 未检测到 Python。请使用「解压即用包」或联系提供者。
    pause
    exit /b 1
)
python XPS_UPS.py

:done
if errorlevel 1 pause
