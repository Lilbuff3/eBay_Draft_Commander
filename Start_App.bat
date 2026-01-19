@echo off
title eBay Draft Commander
cd /d "%~dp0"

echo ====================================================
echo      eBay Draft Commander - Starting Up...
echo ====================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from python.org
    pause
    exit
)

:: Start the browser (delayed to give server time to boot)
echo Launching Dashboard in Browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:5000/app"

:: Start the Server
echo Starting Web Server...
echo.
echo [NOTE] Keep this window OPEN while using the app.
echo [NOTE] Scan the QR code below for Mobile Access.
echo.

python web_server.py
pause
