param(
    [switch]$Https
)

$ErrorActionPreference = "Stop"

$PROJECT_DIR = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$SCRIPT_DIR = $PSScriptRoot
$VBS_PATH = Join-Path $SCRIPT_DIR "run-hidden.vbs"
$BG_LAUNCHER = Join-Path $SCRIPT_DIR "start-background.ps1"
$BACKEND_BAT = Join-Path $SCRIPT_DIR "run-backend.bat"
$CADDY_BAT = Join-Path $SCRIPT_DIR "run-caddy.bat"
$CERT_DIR = Join-Path $PROJECT_DIR ".certs"
$pythonExe = (Get-Command python).Source
$pythonwExe = $pythonExe -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwExe)) { $pythonwExe = $pythonExe }
# run_service.py supervises wsgi_service.py (exit-42 restart contract) —
# always launch the supervisor, never wsgi_service.py directly.
$RUN_SERVICE = Join-Path $PROJECT_DIR "backend\run_service.py"

Write-Host "=== eBay Draft Commander - Register Background Service ===" -ForegroundColor Cyan
Write-Host "Project directory: $PROJECT_DIR" -ForegroundColor DarkGray

# 1. Verify files exist
if (-not (Test-Path $VBS_PATH)) {
    Write-Host "[ERROR] run-hidden.vbs not found at $VBS_PATH" -ForegroundColor Red
    exit 1
}

# 2. Setup HTTPS via `tailscale serve` if requested.
# NOTE: Caddy was abandoned — Windows Firewall auto-created block rules for
# caddy.exe, making inbound 443 unreachable from other tailnet devices.
# `tailscale serve` terminates TLS on the tailnet and reverse-proxies to the
# local backend; its config persists in tailscaled across reboots.
if ($Https) {
    Write-Host "`nConfiguring Tailscale HTTPS (tailscale serve)..." -ForegroundColor Yellow

    # Detect Tailscale
    $TAILSCALE = Get-Command tailscale -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    if (-not $TAILSCALE) {
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
        Write-Host "[ERROR] Cannot find tailscale.exe. Install Tailscale first." -ForegroundColor Red
        exit 1
    }

    # Check Tailscale Login
    $tsJson = & $TAILSCALE status --json 2>$null
    if (-not $tsJson) {
        Write-Host "[ERROR] Tailscale is not running or logged in." -ForegroundColor Red
        exit 1
    }
    $tsStatus = $tsJson | ConvertFrom-Json
    if (-not $tsStatus.Self) {
        Write-Host "[ERROR] Tailscale is not logged in." -ForegroundColor Red
        exit 1
    }

    $hostname = $tsStatus.Self.DNSName.TrimEnd('.')
    Write-Host "[OK] Tailscale hostname: $hostname" -ForegroundColor Green

    # Re-assert the serve mapping (idempotent). tailscale provisions the TLS cert
    # automatically — no manual cert files or Caddyfile needed.
    & $TAILSCALE serve --bg --https=443 http://127.0.0.1:5000
    Write-Host "[OK] tailscale serve configured (443 -> 127.0.0.1:5000)" -ForegroundColor Green
}

# 3. Write run-backend.bat and run-caddy.bat dynamically
Write-Host "`nConfiguring startup batch scripts..." -ForegroundColor Yellow

$backendBatContent = @"
@echo off
cd /d "%~dp0.."
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
if not exist "data" mkdir "data"

"$pythonExe" backend\run_service.py >> data\supervisor_console.log 2>&1
"@
Set-Content -Path $BACKEND_BAT -Value $backendBatContent -Force
Write-Host "[OK] Configured run-backend.bat" -ForegroundColor Green

# 4. Create Scheduled Tasks or Fall back to Startup shortcuts
Write-Host "`nRegistering background service..." -ForegroundColor Yellow

$useScheduledTasks = $true

# Clean up existing Scheduled Tasks if they exist
Get-ScheduledTask -TaskName "eBayDraftCommanderBackend" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Found existing task eBayDraftCommanderBackend. Deleting..." -ForegroundColor DarkGray
    Unregister-ScheduledTask -TaskName "eBayDraftCommanderBackend" -Confirm:$false
}
if ($Https) {
    Get-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Found existing task eBayDraftCommanderCaddy. Deleting..." -ForegroundColor DarkGray
        Unregister-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -Confirm:$false
    }
}

# Clean up Startup shortcuts if they exist
$startupFolder = [Environment]::GetFolderPath("Startup")
$backendShortcutPath = Join-Path $startupFolder "eBay Draft Commander Backend.lnk"
$caddyShortcutPath = Join-Path $startupFolder "eBay Draft Commander Caddy.lnk"

if (Test-Path $backendShortcutPath) {
    Remove-Item $backendShortcutPath -Force -ErrorAction SilentlyContinue
}
if (Test-Path $caddyShortcutPath) {
    Remove-Item $caddyShortcutPath -Force -ErrorAction SilentlyContinue
}

try {
    # Setup standard task settings (triggers at Logon, allows start on battery, restarts if failed)
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

    # Register Backend Task
    $backendAction = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VBS_PATH`" `"$BACKEND_BAT`"" -WorkingDirectory $PROJECT_DIR
    Register-ScheduledTask -TaskName "eBayDraftCommanderBackend" -Action $backendAction -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "[OK] Registered eBayDraftCommanderBackend Scheduled Task" -ForegroundColor Green
    # HTTPS is served by `tailscale serve` (configured above, persists in
    # tailscaled) — no separate scheduled task needed.
} catch {
    # Fallback to Startup folder shortcuts
    Write-Host "[INFO] Scheduled Task registration requires admin permissions. Falling back to Startup folder shortcuts..." -ForegroundColor Yellow
    $useScheduledTasks = $false

    $WshShell = New-Object -ComObject WScript.Shell
    
    # Create Backend Shortcut — uses PowerShell launcher for reliable hidden start
    $backendShortcut = $WshShell.CreateShortcut($backendShortcutPath)
    $backendShortcut.TargetPath = "powershell.exe"
    $backendShortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$BG_LAUNCHER`""
    $backendShortcut.WorkingDirectory = $PROJECT_DIR
    $backendShortcut.WindowStyle = 7 # Minimized/hidden
    $backendShortcut.Save()
    Write-Host "[OK] Created Startup Shortcut: eBay Draft Commander Backend" -ForegroundColor Green
}

# 5. Start the tasks now
Write-Host "`nStarting services in background..." -ForegroundColor Yellow
if ($useScheduledTasks) {
    Start-ScheduledTask -TaskName "eBayDraftCommanderBackend"
} else {
    # Launch the supervisor with pythonw.exe — its child handles log redirection
    Start-Process -FilePath $pythonwExe -ArgumentList "`"$RUN_SERVICE`"" -WindowStyle Hidden -WorkingDirectory $PROJECT_DIR
}

Start-Sleep -Seconds 8

# 6. Check if backend started successfully
$portActive = $false
try {
    $connection = Test-NetConnection -ComputerName "localhost" -Port 5000 -InformationLevel Quiet
    if ($connection) {
        $portActive = $true
    }
} catch {}

if ($portActive) {
    Write-Host "`n=============================================" -ForegroundColor Green
    Write-Host "  Service successfully started in background!" -ForegroundColor Green
    if ($Https) {
        Write-Host "  HTTPS Address: https://$hostname" -ForegroundColor Green
    } else {
        Write-Host "  HTTP Address: http://localhost:5000/app" -ForegroundColor Green
    }
    Write-Host "=============================================" -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] Service started but port 5000 is not yet active." -ForegroundColor Yellow
    Write-Host "          Check logs in data/backend_service.log for details." -ForegroundColor Yellow
}
