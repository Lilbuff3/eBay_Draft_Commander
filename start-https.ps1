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

# ─── Resolve Executables ────────────────────────────────────
# Tailscale CLI (not on PATH by default on Windows)
$TAILSCALE = Get-Command tailscale -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $TAILSCALE) {
    # Check common install locations
    $candidates = @(
        "$env:ProgramFiles\Tailscale\tailscale.exe",
        "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe",
        "$env:LOCALAPPDATA\Tailscale\tailscale.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $TAILSCALE = $c; break }
    }
}
if (-not $TAILSCALE -or -not (Test-Path $TAILSCALE)) {
    Write-Host "[ERROR] Cannot find tailscale.exe. Install from https://tailscale.com/download" -ForegroundColor Red
    exit 1
}

# Caddy (winget installs to WinGet\Links or Packages)
$CADDY = Get-Command caddy -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $CADDY) {
    $candidates = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\caddy.exe",
        (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "caddy.exe" -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName)
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { $CADDY = $c; break }
    }
}
if (-not $CADDY -or -not (Test-Path $CADDY)) {
    Write-Host "[ERROR] Cannot find caddy.exe. Install with 'winget install Caddy'" -ForegroundColor Red
    exit 1
}

# ─── Check Prerequisites ────────────────────────────────────
Write-Host "`n=== eBay Draft Commander - HTTPS Startup ===" -ForegroundColor Cyan
Write-Host "  Tailscale: $TAILSCALE" -ForegroundColor DarkGray
Write-Host "  Caddy:     $CADDY" -ForegroundColor DarkGray

# Check Tailscale login
$tsJson = & $TAILSCALE status --json 2>$null
if (-not $tsJson) {
    Write-Host "[ERROR] Tailscale is not running or not logged in." -ForegroundColor Red
    Write-Host "        Run: & '$TAILSCALE' login" -ForegroundColor Yellow
    exit 1
}
$tsStatus = $tsJson | ConvertFrom-Json
if (-not $tsStatus.Self) {
    Write-Host "[ERROR] Tailscale is not logged in. Run: & '$TAILSCALE' login" -ForegroundColor Red
    exit 1
}

$hostname = $tsStatus.Self.DNSName.TrimEnd('.')
Write-Host "[OK] Tailscale hostname: $hostname" -ForegroundColor Green

# ─── Generate TLS Certs ─────────────────────────────────────
New-Item -ItemType Directory -Force -Path $CERT_DIR | Out-Null

$certFile = Join-Path $CERT_DIR "$hostname.crt"
$keyFile = Join-Path $CERT_DIR "$hostname.key"

if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
    Write-Host "[...] Generating TLS certificate for $hostname" -ForegroundColor Yellow
    Push-Location $CERT_DIR
    & $TAILSCALE cert $hostname
    Pop-Location
    
    if (-not (Test-Path $certFile)) {
        # Tailscale cert might output to current dir instead
        $possibleCert = Join-Path $PROJECT_DIR "$hostname.crt"
        $possibleKey = Join-Path $PROJECT_DIR "$hostname.key"
        if (Test-Path $possibleCert) {
            Move-Item $possibleCert $certFile -Force
            Move-Item $possibleKey $keyFile -Force
        }
    }
    
    if (Test-Path $certFile) {
        Write-Host "[OK] TLS certificate generated" -ForegroundColor Green
    }
    else {
        Write-Host "[ERROR] Failed to generate TLS certificate." -ForegroundColor Red
        Write-Host "        Make sure HTTPS Certificates are enabled at:" -ForegroundColor Yellow
        Write-Host "        https://login.tailscale.com/admin/dns" -ForegroundColor Yellow
        exit 1
    }
}
else {
    Write-Host "[OK] TLS certificate already exists" -ForegroundColor Green
}

# ─── Generate Caddyfile ─────────────────────────────────────
$caddyfile = Join-Path $PROJECT_DIR "Caddyfile"
# Normalize paths to forward slashes for Caddy
$certPath = $certFile -replace '\\', '/'
$keyPath = $keyFile -replace '\\', '/'

$caddyConfig = @"
$hostname {
    tls $certPath $keyPath
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
$caddy = Start-Process -FilePath $CADDY `
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
}
finally {
    Write-Host "`n[...] Shutting down..." -ForegroundColor Yellow
    Stop-Process -Id $flask.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $caddy.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] All processes stopped" -ForegroundColor Green
}
