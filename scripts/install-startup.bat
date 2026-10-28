@echo off
setlocal
cd /d "%~dp0\.."
set "REPO_DIR=%CD%"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\Claude Usage Bar.lnk"
set "RUN_BAT=%REPO_DIR%\run.bat"

if not exist "%RUN_BAT%" (
    echo [!] Khong tim thay run.bat tai %REPO_DIR%
    pause
    exit /b 1
)

echo ==^> Cai dat tu dong khoi dong cung Windows...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%RUN_BAT%'; $s.WorkingDirectory = '%REPO_DIR%'; $s.WindowStyle = 7; $s.Description = 'Claude Usage Bar Startup'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [OK] Da tao shortcut khoi dong tai:
    echo      %SHORTCUT_PATH%
    echo ==^> Claude Usage Bar se tu dong chay khi dang nhap Windows.
) else (
    echo [!] Tao shortcut that bai.
)
