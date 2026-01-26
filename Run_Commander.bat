@echo off
title eBay Draft Commander - Inbox Processor
echo ===================================================
echo   eBay Draft Commander: B.L.A.S.T. Protocol
echo ===================================================
echo.
echo [1] Checking Environment...
python --version

echo.
echo [2] Starting Inbox Processor...
echo.

python tools/process_inbox.py

echo.
echo ===================================================
echo   Process Complete.
echo ===================================================
pause
