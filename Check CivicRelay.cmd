@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" -CheckOnly
set "result=%errorlevel%"
pause
exit /b %result%
