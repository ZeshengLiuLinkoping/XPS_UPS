@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   制作「解压即用包」（给她用，免安装）
echo ========================================
echo.

set "PORTABLE=%~dp0XPS_UPS_便携"
set "PYEXE=%PORTABLE%\python\python.exe"

if not exist "%PORTABLE%" mkdir "%PORTABLE%"
if not exist "%PORTABLE%\python\python.exe" (
    echo [步骤1] 请先把「Python 嵌入式包」解压到下面文件夹里的 python 子文件夹：
    echo   %PORTABLE%\python\
    echo.
    echo 下载地址：https://www.python.org/downloads/windows/
    echo 选 "Windows embeddable package (64-bit)"，下载后解压到 %PORTABLE%\python\
    echo.
    echo 解压完成后，再运行本脚本一次。
    explorer "%PORTABLE%"
    pause
    exit /b 0
)

echo [步骤2] 复制程序文件...
copy /y XPS_UPS.py "%PORTABLE%\" >nul
copy /y app.py "%PORTABLE%\" >nul
copy /y reader.py "%PORTABLE%\" >nul
copy /y plots.py "%PORTABLE%\" >nul
copy /y export_csv.py "%PORTABLE%\" >nul
copy /y requirements.txt "%PORTABLE%\" >nul
copy /y 运行.bat "%PORTABLE%\" >nul
copy /y 给她用-免安装说明.txt "%PORTABLE%\" >nul
echo    已复制 XPS_UPS.py, app.py, reader.py, plots.py, export_csv.py, requirements.txt, 运行.bat

echo.
echo [步骤3] 用便携 Python 安装依赖（首次约 1~2 分钟）...
"%PYEXE%" -m ensurepip --default-pip 2>nul
"%PYEXE%" -m pip install --quiet -r "%PORTABLE%\requirements.txt" 2>nul
if errorlevel 1 (
    echo    若失败，请手动在「XPS_UPS_便携」目录打开命令行，执行：
    echo    python\python.exe -m ensurepip
    echo    python\python.exe -m pip install -r requirements.txt
) else (
    echo    依赖已安装完成。
)

echo.
echo ========================================
echo 完成。请把「XPS_UPS_便携」整个文件夹打成 zip 发给她。
echo 她解压后双击「运行.bat」即可使用，无需安装、无需管理员。
echo ========================================
explorer "%PORTABLE%"
pause
