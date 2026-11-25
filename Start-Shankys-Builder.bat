@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 studio.py
) else (
  python studio.py
)
if errorlevel 1 pause
