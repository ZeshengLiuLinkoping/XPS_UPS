@echo off
chcp 65001 >nul
echo ========================================
echo   UPS IBW Processor - 打包为 exe
echo ========================================
cd /d "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 PyInstaller。请先安装：
    echo   pip install pyinstaller
    pause
    exit /b 1
)

echo.
echo 正在打包（单文件 exe，约需 1~3 分钟）...
echo.
pyinstaller --noconfirm XPS_UPS.spec

if errorlevel 1 (
    echo.
    echo 打包失败，请检查上方报错。
    pause
    exit /b 1
)

echo.
echo 打包完成。
echo 可执行文件位置： dist\UPS_IBW_Processor.exe
echo 可将 dist 文件夹中的 UPS_IBW_Processor.exe 发给别人使用（无需安装 Python）。
echo.
explorer dist
pause
