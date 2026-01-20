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
echo [2/3] Opening User Manual...
start markdown_viewer.html USER_MANUAL.md || start USER_MANUAL.md

echo.
echo [3/3] Launching Production Environment...
call Start_Production.bat
