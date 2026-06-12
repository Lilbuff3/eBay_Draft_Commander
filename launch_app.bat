@echo off
title eBay Draft Commander
cd /d "%~dp0"

echo ============================================
echo   eBay Draft Commander - Starting...
echo ============================================
echo.

:: Activate virtual environment if present (global Python works too)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Check if server is already running
curl -s http://localhost:5000/api/system/health >nul 2>&1
if %errorlevel%==0 (
    echo Server already running! Opening browser...
    start "" http://localhost:5000/app
    timeout /t 3
    exit
)

:: Start the backend server in THIS window
echo Starting backend server on port 5000...
echo Close this window to stop the server.
echo.

:: Open browser after a delay (in background)
start "" cmd /c "timeout /t 5 >nul && start http://localhost:5000/app"

:: Run server in foreground (keeps window open)
python backend\wsgi.py

:: If we get here, server crashed
echo.
echo ============================================
echo   SERVER STOPPED OR CRASHED
echo ============================================
echo.
pause
