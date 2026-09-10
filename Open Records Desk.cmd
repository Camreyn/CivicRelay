@echo off
powershell.exe -NoProfile -File "%~dp0Open-Records-Desk.ps1"
if errorlevel 1 pause
