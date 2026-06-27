@echo off
title Draft Commander Launcher
cd /d "C:\Users\adam\Projects\ebay-draft-commander"

echo Starting Draft Commander (supervised, runs hidden in background)...
start "" "C:\Program Files\Python312\pythonw.exe" "backend\run_service.py"

echo Waiting for the server to come up...
powershell -NoProfile -Command "for($i=0;$i -lt 30;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/api/system/health -TimeoutSec 2 | Out-Null; Write-Host 'Server up.'; break}catch{Start-Sleep 1}}"

echo Opening app...
start "" "http://127.0.0.1:5000/app/"
