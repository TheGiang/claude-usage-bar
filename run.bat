@echo off
REM Bootstrap cho Windows — double-click hoac chay: run.bat
cd /d "%~dp0"
where py >nul 2>nul && (py run.py %* & goto :eof)
python run.py %*
