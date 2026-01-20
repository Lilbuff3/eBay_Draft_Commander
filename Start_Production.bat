@echo off
setlocal EnableDelayedExpansion

REM Get timestamp for log file (YYYYMMDD_HHMMSS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "timestamp=%datetime:~0,8%_%datetime:~8,6%"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir "logs"
set "LOG_FILE=logs\session_%timestamp%.log"

echo ===========================================
echo   eBay Draft Commander - Production Start
echo   Started: %date% %time%
echo   Log: %LOG_FILE%
echo ===========================================
echo.

REM 1. System Health Check
echo [1/4] Running System Health Check...
echo [1/4] Running System Health Check... >> "%LOG_FILE%"
python verify_system_health.py >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] System Health Check FAILED! 
    echo Please review the errors above or in %LOG_FILE%
    echo.
    pause
    exit /b 1
) else (
    echo    Health Check PASSED.
)

REM 2. Set Environment
echo [2/4] Setting Production Environment...
set FLASK_ENV=production
set LOG_LEVEL=INFO

REM 3. Start Backend
echo [3/4] Starting Web Server...
echo [3/4] Starting Web Server... >> "%LOG_FILE%"
start "eBay Backend Server" cmd /k "python web_server.py >> "%LOG_FILE%" 2>&1"

REM 4. Launch Frontend
echo [4/4] Waiting for server & Launching Browser...
timeout /t 5 /nobreak > nul

REM Find Local IP for reference
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
)

echo.
echo ===========================================
echo   SYSTEM IS READY
echo ===========================================
echo   Desktop: http://localhost:5000/app
echo   Mobile:  http://%IP%:5000/app
echo ===========================================
echo.
echo Opening browser...
start http://localhost:5000/app

echo.
echo Server running in background. Logs: %LOG_FILE%
echo Close this window when finished.
pause
