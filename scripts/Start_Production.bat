echo Starting Backend Server...
pushd ..
python backend/wsgi.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server crashed or failed to start.
    pause
)
