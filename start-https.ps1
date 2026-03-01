<#
.SYNOPSIS
    Start eBay Draft Commander with HTTPS via Tailscale + Caddy
.DESCRIPTION
    1. Detects your Tailscale hostname and generates TLS certs
    2. Creates a Caddyfile for HTTPS reverse proxy
    3. Starts the Flask backend
    4. Starts Caddy to provide HTTPS
#>

$ErrorActionPreference = "Stop"

# ─── Configuration ──────────────────────────────────────────
$FLASK_PORT = 5000
$PROJECT_DIR = $PSScriptRoot
$CERT_DIR = Join-Path $PROJECT_DIR ".certs"

# ─── Check Prerequisites ────────────────────────────────────
Write-Host "`n=== eBay Draft Commander - HTTPS Startup ===" -ForegroundColor Cyan

# Check Tailscale
$tsStatus = tailscale status --json 2>$null | ConvertFrom-Json
if (-not $tsStatus -or -not $tsStatus.Self) {
    Write-Host "[ERROR] Tailscale is not logged in. Run 'tailscale login' first." -ForegroundColor Red
    exit 1
}

$hostname = $tsStatus.Self.DNSName.TrimEnd('.')
Write-Host "[OK] Tailscale hostname: $hostname" -ForegroundColor Green

# Check Caddy
if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Caddy is not installed. Run 'winget install Caddy'" -ForegroundColor Red
    exit 1
}

# ─── Generate TLS Certs ─────────────────────────────────────
New-Item -ItemType Directory -Force -Path $CERT_DIR | Out-Null

$certFile = Join-Path $CERT_DIR "$hostname.crt"
$keyFile = Join-Path $CERT_DIR "$hostname.key"

if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
    Write-Host "[...] Generating TLS certificate for $hostname" -ForegroundColor Yellow
    Push-Location $CERT_DIR
    tailscale cert $hostname
    Pop-Location
    Write-Host "[OK] TLS certificate generated" -ForegroundColor Green
} else {
    Write-Host "[OK] TLS certificate already exists" -ForegroundColor Green
}

# ─── Generate Caddyfile ─────────────────────────────────────
$caddyfile = Join-Path $PROJECT_DIR "Caddyfile"
$caddyConfig = @"
$hostname {
    tls $certFile $keyFile
    reverse_proxy localhost:$FLASK_PORT
}
"@

Set-Content -Path $caddyfile -Value $caddyConfig
Write-Host "[OK] Caddyfile generated" -ForegroundColor Green

# ─── Start Flask Backend ────────────────────────────────────
Write-Host "`n[...] Starting Flask backend on port $FLASK_PORT" -ForegroundColor Yellow
$flask = Start-Process -FilePath "python" `
    -ArgumentList "backend/wsgi.py" `
    -WorkingDirectory $PROJECT_DIR `
    -PassThru `
    -WindowStyle Normal

Start-Sleep -Seconds 2

if ($flask.HasExited) {
    Write-Host "[ERROR] Flask failed to start" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Flask backend started (PID: $($flask.Id))" -ForegroundColor Green

# ─── Start Caddy ────────────────────────────────────────────
Write-Host "[...] Starting Caddy HTTPS reverse proxy" -ForegroundColor Yellow
$caddy = Start-Process -FilePath "caddy" `
    -ArgumentList "run --config `"$caddyfile`"" `
    -WorkingDirectory $PROJECT_DIR `
    -PassThru `
    -WindowStyle Normal

Start-Sleep -Seconds 2

if ($caddy.HasExited) {
    Write-Host "[ERROR] Caddy failed to start" -ForegroundColor Red
    Stop-Process -Id $flask.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "[OK] Caddy started (PID: $($caddy.Id))" -ForegroundColor Green

# ─── Ready ──────────────────────────────────────────────────
Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "  HTTPS ready at: https://$hostname" -ForegroundColor Green
Write-Host "  Open this URL on your phone to install the PWA" -ForegroundColor White
Write-Host "=============================================`n" -ForegroundColor Cyan

Write-Host "Press Ctrl+C to stop both servers..." -ForegroundColor Gray

try {
    # Wait for either process to exit
    while (-not $flask.HasExited -and -not $caddy.HasExited) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`n[...] Shutting down..." -ForegroundColor Yellow
    Stop-Process -Id $flask.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $caddy.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] All processes stopped" -ForegroundColor Green
}
