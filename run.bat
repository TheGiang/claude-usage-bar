@echo off
REM Bootstrap for Windows. Double-click, or run: run.bat
cd /d "%~dp0"

REM Chon Python chay duoc that su (py launcher co the tro toi ban Python da bi go / cua tai khoan khac)
set "PYCMD="
py -3 -c "import sys" >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
    python -c "import sys" >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD (
    echo [!] Khong tim thay Python chay duoc.
    set "BAD=1"
) else (
    %PYCMD% run.py %*
    if errorlevel 1 set "BAD=1"
)

if defined BAD (
    echo.
    echo [!] Khong chay duoc - xem thong bao loi o tren.
    echo     Neu bao khong tim thay Python: cai Python 3 tu https://www.python.org/downloads/
    echo     va tick "Add python.exe to PATH" khi cai.
    pause
)
