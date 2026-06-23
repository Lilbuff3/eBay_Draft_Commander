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
$WSGI_SERVICE = Join-Path $PROJECT_DIR "backend\wsgi_service.py"

Write-Host "=== eBay Draft Commander - Register Background Service ===" -ForegroundColor Cyan
Write-Host "Project directory: $PROJECT_DIR" -ForegroundColor DarkGray

# 1. Verify files exist
if (-not (Test-Path $VBS_PATH)) {
    Write-Host "[ERROR] run-hidden.vbs not found at $VBS_PATH" -ForegroundColor Red
    exit 1
}

# 2. Setup HTTPS / Tailscale / Caddy if requested
$caddyExe = $null
if ($Https) {
    Write-Host "`nConfiguring Tailscale HTTPS and Caddy..." -ForegroundColor Yellow

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

    # Detect Caddy
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
        Write-Host "[ERROR] Cannot find caddy.exe. Install Caddy with 'winget install Caddy'" -ForegroundColor Red
        exit 1
    }
    $caddyExe = $CADDY

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

    # Generate TLS Certs
    New-Item -ItemType Directory -Force -Path $CERT_DIR | Out-Null
    $certFile = Join-Path $CERT_DIR "$hostname.crt"
    $keyFile = Join-Path $CERT_DIR "$hostname.key"

    if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
        Write-Host "[...] Generating TLS certificate for $hostname" -ForegroundColor Yellow
        Push-Location $CERT_DIR
        & $TAILSCALE cert $hostname
        Pop-Location
        
        if (-not (Test-Path $certFile)) {
            $possibleCert = Join-Path $PROJECT_DIR "$hostname.crt"
            $possibleKey = Join-Path $PROJECT_DIR "$hostname.key"
            if (Test-Path $possibleCert) {
                Move-Item $possibleCert $certFile -Force
                Move-Item $possibleKey $keyFile -Force
            }
        }
    }

    if (-not (Test-Path $certFile)) {
        Write-Host "[ERROR] Failed to generate Tailscale certificates." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] TLS certificates ready" -ForegroundColor Green

    # Write Caddyfile
    $caddyfile = Join-Path $PROJECT_DIR "Caddyfile"
    $certPath = $certFile -replace '\\', '/'
    $keyPath = $keyFile -replace '\\', '/'
    $caddyConfig = @"
$hostname {
    tls $certPath $keyPath
    reverse_proxy localhost:5000
}
"@
    Set-Content -Path $caddyfile -Value $caddyConfig
    Write-Host "[OK] Caddyfile generated" -ForegroundColor Green
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

"$pythonExe" backend\wsgi.py >> data\backend_service.log 2>&1
"@
Set-Content -Path $BACKEND_BAT -Value $backendBatContent -Force
Write-Host "[OK] Configured run-backend.bat" -ForegroundColor Green

if ($Https) {
    $caddyBatContent = @"
@echo off
cd /d "%~dp0.."
if not exist "data" mkdir "data"

"$caddyExe" run --config Caddyfile >> data\caddy_service.log 2>&1
"@
    Set-Content -Path $CADDY_BAT -Value $caddyBatContent -Force
    Write-Host "[OK] Configured run-caddy.bat" -ForegroundColor Green
}

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

    # Register Caddy Task if HTTPS is requested
    if ($Https) {
        $caddyAction = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VBS_PATH`" `"$CADDY_BAT`"" -WorkingDirectory $PROJECT_DIR
        Register-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -Action $caddyAction -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
        Write-Host "[OK] Registered eBayDraftCommanderCaddy Scheduled Task" -ForegroundColor Green
    }
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
    if ($Https) {
        Start-ScheduledTask -TaskName "eBayDraftCommanderCaddy"
    }
} else {
    # Use pythonw.exe with wsgi_service.py — handles its own log redirection
    Start-Process -FilePath $pythonwExe -ArgumentList "`"$WSGI_SERVICE`"" -WindowStyle Hidden -WorkingDirectory $PROJECT_DIR
    if ($Https) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$CADDY_BAT`"" -WindowStyle Hidden -WorkingDirectory $PROJECT_DIR
    }
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
