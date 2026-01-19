@echo off
echo ====================================
echo eBay Draft Commander - Production Mode
echo ====================================
echo.

REM Set production environment
set FLASK_ENV=production
set LOG_LEVEL=INFO

echo [1/3] Checking Python...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo [2/3] Starting Backend Server...
start "eBay Draft Commander Backend" cmd /k "python web_server.py"

REM Wait for server to start
echo [3/3] Waiting for server startup...
timeout /t 5 /nobreak > nul

echo.
echo ====================================
echo eBay Draft Commander is RUNNING
echo ====================================
echo.
echo Desktop Access: http://localhost:5000/app
echo Mobile Access:  http://YOUR-IP:5000/app
echo.
echo To find your IP address:
echo   ipconfig ^| findstr IPv4
echo.
echo Press any key to open in browser...
pause > nul

start http://localhost:5000/app

echo.
echo Server is running in background window.
echo Close this window when done (server will keep running).
echo.
pause
