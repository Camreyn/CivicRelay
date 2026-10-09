@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply-update.ps1"
set "result=%ERRORLEVEL%"
pause
exit /b %result%
