param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("status", "start", "stop", "restart", "logs")]
    [string]$Action,

    [switch]$Caddy
)

$ErrorActionPreference = "Stop"

$PROJECT_DIR = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$SCRIPT_DIR = $PSScriptRoot
$VBS_PATH = Join-Path $SCRIPT_DIR "run-hidden.vbs"
$BACKEND_BAT = Join-Path $SCRIPT_DIR "run-backend.bat"
$CADDY_BAT = Join-Path $SCRIPT_DIR "run-caddy.bat"
$LOG_BACKEND = Join-Path $PROJECT_DIR "data\backend_service.log"
$LOG_CADDY = Join-Path $PROJECT_DIR "data\caddy_service.log"
$pythonExe = (Get-Command python).Source
$pythonwExe = $pythonExe -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwExe)) { $pythonwExe = $pythonExe }
$WSGI_SERVICE = Join-Path $PROJECT_DIR "backend\wsgi_service.py"

$startupFolder = [Environment]::GetFolderPath("Startup")
$backendShortcutPath = Join-Path $startupFolder "eBay Draft Commander Backend.lnk"
$caddyShortcutPath = Join-Path $startupFolder "eBay Draft Commander Caddy.lnk"

function Get-TaskStatus([string]$taskName) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
        return [PSCustomObject]@{
            Registered = $true
            State = $task.State
            LastRunTime = $info.LastRunTime
            LastTaskResult = $info.LastTaskResult
        }
    }
    return [PSCustomObject]@{
        Registered = $false
        State = "Not Registered"
        LastRunTime = $null
        LastTaskResult = $null
    }
}

switch ($Action) {
    "status" {
        Write-Host "=== eBay Draft Commander - Service Status ===" -ForegroundColor Cyan
        
        # 1. Check Scheduled Tasks
        $backendTask = Get-TaskStatus "eBayDraftCommanderBackend"
        $caddyTask = Get-TaskStatus "eBayDraftCommanderCaddy"
        
        $backendShortcutExists = Test-Path $backendShortcutPath
        $caddyShortcutExists = Test-Path $caddyShortcutPath

        Write-Host "Service Installation Type:" -ForegroundColor Yellow
        if ($backendTask.Registered) {
            Write-Host "  [Scheduled Task] Backend is registered." -ForegroundColor Green
            Write-Host "    State: $($backendTask.State)" -ForegroundColor Yellow
            Write-Host "    Last Run: $($backendTask.LastRunTime) (Result Code: $($backendTask.LastTaskResult))" -ForegroundColor DarkGray
            if ($caddyTask.Registered) {
                Write-Host "  [Scheduled Task] Caddy is registered. State: $($caddyTask.State)" -ForegroundColor Green
            }
        } elseif ($backendShortcutExists) {
            Write-Host "  [Startup Shortcut] Backend is registered in Startup folder." -ForegroundColor Green
            if ($caddyShortcutExists) {
                Write-Host "  [Startup Shortcut] Caddy is registered in Startup folder." -ForegroundColor Green
            }
        } else {
            Write-Host "  Not registered as Scheduled Task or Startup Shortcut." -ForegroundColor Red
        }

        # 2. Check Port 5000 Active Listener
        Write-Host "`nNetwork Status:" -ForegroundColor Yellow
        $netstat = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
        if ($netstat) {
            $owningPid = $netstat.OwningProcess
            $proc = Get-Process -Id $owningPid -ErrorAction SilentlyContinue
            $procName = if ($proc) { $proc.ProcessName } else { "Unknown" }
            Write-Host "  Port 5000 (Backend): listening on PID $owningPid ($procName)" -ForegroundColor Green
        } else {
            Write-Host "  Port 5000 (Backend): Not Listening" -ForegroundColor Red
        }

        # Check Caddy Process
        $caddyProc = Get-Process -Name "caddy" -ErrorAction SilentlyContinue
        if ($caddyProc) {
            Write-Host "  Caddy Process: Running on PID $($caddyProc.Id)" -ForegroundColor Green
        } else {
            if ($caddyShortcutExists -or $caddyTask.Registered) {
                Write-Host "  Caddy Process: Not Running" -ForegroundColor Red
            }
        }

        # 3. Log Excerpts
        Write-Host "`nBackend Service Log (last 5 lines):" -ForegroundColor Yellow
        if (Test-Path $LOG_BACKEND) {
            Get-Content $LOG_BACKEND -Tail 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
        } else {
            Write-Host "  Log file not found." -ForegroundColor DarkGray
        }

        if ($caddyTask.Registered -or $caddyShortcutExists) {
            Write-Host "`nCaddy Service Log (last 5 lines):" -ForegroundColor Yellow
            if (Test-Path $LOG_CADDY) {
                Get-Content $LOG_CADDY -Tail 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
            } else {
                Write-Host "  Log file not found." -ForegroundColor DarkGray
            }
        }
    }

    "start" {
        Write-Host "=== Starting Background Services ===" -ForegroundColor Cyan
        $backendTask = Get-TaskStatus "eBayDraftCommanderBackend"
        $backendShortcutExists = Test-Path $backendShortcutPath

        if ($backendTask.Registered) {
            Write-Host "Starting eBayDraftCommanderBackend task..." -ForegroundColor Yellow
            Start-ScheduledTask -TaskName "eBayDraftCommanderBackend"
            
            $caddyTask = Get-TaskStatus "eBayDraftCommanderCaddy"
            if ($caddyTask.Registered) {
                Write-Host "Starting eBayDraftCommanderCaddy task..." -ForegroundColor Yellow
                Start-ScheduledTask -TaskName "eBayDraftCommanderCaddy"
            }
        } elseif ($backendShortcutExists) {
            Write-Host "Starting eBay Draft Commander Backend..." -ForegroundColor Yellow
            Start-Process -FilePath $pythonwExe -ArgumentList "`"$WSGI_SERVICE`"" -WindowStyle Hidden -WorkingDirectory $PROJECT_DIR
            
            $caddyShortcutExists = Test-Path $caddyShortcutPath
            if ($caddyShortcutExists) {
                Write-Host "Starting eBay Draft Commander Caddy..." -ForegroundColor Yellow
                Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$CADDY_BAT`"" -WindowStyle Hidden -WorkingDirectory $PROJECT_DIR
            }
        } else {
            Write-Host "[ERROR] Service is not registered. Run scripts/register-service.ps1 first." -ForegroundColor Red
            exit 1
        }
        
        Start-Sleep -Seconds 2
        Write-Host "[OK] Start commands issued. Run status to verify." -ForegroundColor Green
    }

    "stop" {
        Write-Host "=== Stopping Background Services ===" -ForegroundColor Cyan
        $backendTask = Get-TaskStatus "eBayDraftCommanderBackend"
        if ($backendTask.Registered) {
            Write-Host "Stopping eBayDraftCommanderBackend task..." -ForegroundColor Yellow
            Stop-ScheduledTask -TaskName "eBayDraftCommanderBackend" -ErrorAction SilentlyContinue
        }
        $caddyTask = Get-TaskStatus "eBayDraftCommanderCaddy"
        if ($caddyTask.Registered) {
            Write-Host "Stopping eBayDraftCommanderCaddy task..." -ForegroundColor Yellow
            Stop-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -ErrorAction SilentlyContinue
        }

        # Kill any processes listening on port 5000
        $netstat = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
        if ($netstat) {
            $owningPid = $netstat.OwningProcess
            Write-Host "Killing backend process on PID $owningPid..." -ForegroundColor Yellow
            Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
        }

        # Kill caddy process if running
        $caddyProc = Get-Process -Name "caddy" -ErrorAction SilentlyContinue
        if ($caddyProc) {
            Write-Host "Killing caddy process..." -ForegroundColor Yellow
            Stop-Process -Name "caddy" -Force -ErrorAction SilentlyContinue
        }
        
        Write-Host "[OK] Services stopped." -ForegroundColor Green
    }

    "restart" {
        & $MyInvocation.MyCommand.Path "stop"
        Start-Sleep -Seconds 2
        & $MyInvocation.MyCommand.Path "start"
    }

    "logs" {
        $targetLog = if ($Caddy) { $LOG_CADDY } else { $LOG_BACKEND }
        $logName = if ($Caddy) { "Caddy Service" } else { "Backend Service" }
        
        Write-Host "=== Tailing $logName Logs (Ctrl+C to exit) ===" -ForegroundColor Cyan
        if (Test-Path $targetLog) {
            Get-Content $targetLog -Tail 20 -Wait
        } else {
            Write-Host "Log file '$targetLog' does not exist yet." -ForegroundColor Red
        }
    }
}
