@echo off
title Stop Draft Commander
echo Stopping Draft Commander...

REM Kill the supervisor FIRST so it does not relaunch the child on exit.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_service\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

REM Then kill the server child (wsgi_service.py).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'wsgi_service\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Stopped.
timeout /t 2 >nul
