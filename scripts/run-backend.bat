@echo off
cd /d "%~dp0.."
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
if not exist "data" mkdir "data"

"C:\Program Files\Python312\python.exe" backend\run_service.py >> data\supervisor_console.log 2>&1
