# eBay Draft Commander - Background Service Launcher
# This script is invoked by the Startup folder shortcut or service-control.ps1.
# It launches the Flask backend as a fully headless background process.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = (Resolve-Path (Join-Path $scriptDir "..")).ProviderPath
$wsgiService = Join-Path $projectDir "backend\wsgi_service.py"
$caddyBat = Join-Path $scriptDir "run-caddy.bat"

# Resolve Python path — prefer pythonw.exe (windowless) for background use
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
$pythonwExe = $pythonExe -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwExe)) {
    $pythonwExe = $pythonExe  # Fallback to regular python
}

# Start backend hidden — wsgi_service.py handles its own log redirection
if (Test-Path $wsgiService) {
    Start-Process -FilePath $pythonwExe -ArgumentList "`"$wsgiService`"" -WindowStyle Hidden -WorkingDirectory $projectDir
}

# Start caddy hidden (only if bat exists and has content beyond the template)
if ((Test-Path $caddyBat) -and (Get-Item $caddyBat).Length -gt 50) {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$caddyBat`"" -WindowStyle Hidden -WorkingDirectory $projectDir
}
