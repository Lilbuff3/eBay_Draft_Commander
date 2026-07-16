# eBay Draft Commander - Background Service Launcher
# This script is invoked by the Startup folder shortcut or service-control.ps1.
# It launches the Flask backend as a fully headless background process.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = (Resolve-Path (Join-Path $scriptDir "..")).ProviderPath
# run_service.py is the supervisor: spawns wsgi_service.py as a child and
# relaunches it on exit-42, which is what makes POST /api/system/restart work.
# Launching wsgi_service.py directly leaves the backend un-restartable.
$runService = Join-Path $projectDir "backend\run_service.py"

# Resolve Python path — prefer pythonw.exe (windowless) for background use
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
$pythonwExe = $pythonExe -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwExe)) {
    $pythonwExe = $pythonExe  # Fallback to regular python
}

# Start supervisor hidden — its wsgi_service.py child handles log redirection
if (Test-Path $runService) {
    Start-Process -FilePath $pythonwExe -ArgumentList "`"$runService`"" -WindowStyle Hidden -WorkingDirectory $projectDir
}

# HTTPS is handled by `tailscale serve` (persists in tailscaled across reboots),
# not Caddy — Windows Firewall block-rules on caddy.exe made inbound 443 unreachable
# from other tailnet devices.
#
# Re-assert the tailscale serve mapping on every launch so the phone endpoint is
# self-healing: if tailscaled's persisted config is ever lost/reset, HTTPS would
# otherwise silently die with nothing to restore it. The command is idempotent —
# re-running it with the same target is a no-op.
$tailscaleExe = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $tailscaleExe) {
    $candidate = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
    if (Test-Path $candidate) { $tailscaleExe = $candidate }
}
if ($tailscaleExe) {
    try {
        & $tailscaleExe serve --bg --https=443 http://127.0.0.1:5000 | Out-Null
    } catch {
        # Best-effort: if tailscaled isn't up yet, the persisted config still
        # applies once it starts. Don't block backend launch on this.
    }
}
