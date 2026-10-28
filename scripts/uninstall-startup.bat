@echo off
setlocal
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Claude Usage Bar.lnk"

echo ==^> Go tu dong khoi dong tren Windows...
if exist "%SHORTCUT_PATH%" (
    del /f /q "%SHORTCUT_PATH%"
    echo [OK] Da xoa shortcut khoi dong: %SHORTCUT_PATH%
) else (
    echo [i] Khong tim thay shortcut khoi dong trong thu muc Startup.
)

powershell -NoProfile -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*claude_usage_app.py*' }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('[OK] Da dung tien trinh PID: ' + $p.ProcessId) } } else { Write-Host '[i] Khong co tien trinh Claude Usage Bar nao dang chay.' }"

echo ==^> Hoan tat go bo khoi dong va tat ung dung.
