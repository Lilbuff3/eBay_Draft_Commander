@echo off
cd /d "%~dp0"
echo Starting eBay Draft Commander...

:: Check for virtual environment and activate if present
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment (venv)...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
)

echo Starting Backend Server...
:: Run in a new window but keep it open on error
start "eBay Draft Commander Backend" cmd /k "python backend\wsgi.py || (echo. & echo ------------------------------------------------ & echo CRITICAL ERROR: Backend failed to start! & echo ------------------------------------------------ & echo. & pause & exit)"

echo Waiting for server to initialize...
timeout /t 5 >nul

echo Opening Dashboard...
start http://localhost:5000/app

echo.
echo If the browser shows an error, check the "eBay Draft Commander Backend" window.
echo You can close this launcher window now.
timeout /t 10
exit
