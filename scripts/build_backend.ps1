
# Build Backend Script
# Compiles the Python Flask app into a standalone executable using PyInstaller

Write-Host "Building Backend..." -ForegroundColor Cyan

# Ensure we are in the project root
$SCRIPT_DIR = $PSScriptRoot
$PROJECT_ROOT = Split-Path $SCRIPT_DIR -Parent
Set-Location $PROJECT_ROOT

# Output Directory (relative to project root)
$DIST_DIR = "frontend/dist-python"

# Clean previous build
if (Test-Path $DIST_DIR) {
    Remove-Item -Recurse -Force $DIST_DIR
}
New-Item -ItemType Directory -Force -Path $DIST_DIR | Out-Null

# Run PyInstaller
# --onefile: Create a single .exe
# --name web_server: Output name
# --distpath: Where to put the .exe
# --paths tools: Add tools/ directory to python path (for create_from_folder)
# --hidden-import: Explicitly include dynamic dependencies if needed
# --clean: Clean cache

Write-Host "Running PyInstaller..."
python -m PyInstaller --noconfirm `
    --name web_server `
    --onefile `
    --clean `
    --distpath $DIST_DIR `
    --workpath "./build" `
    --paths "./tools" `
    --hidden-import "engineio.async_drivers.threading" `
    --hidden-import "create_from_folder" `
    "backend/wsgi.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backend Build Successful!" -ForegroundColor Green
    Write-Host "Output: $DIST_DIR/web_server.exe"
}
else {
    Write-Host "Backend Build Failed!" -ForegroundColor Red
    exit 1
}
