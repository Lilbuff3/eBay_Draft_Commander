@echo off
echo ===========================================
echo   eBay Draft Commander - Selling Session
echo ===========================================
echo.

echo [1/3] Checking for updates...
git pull
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Git pull failed - continuing with local version.
) else (
    echo [OK] Code is up to date.
)

echo.
echo [2/2] Launching Production Environment...
call Start_Production.bat
