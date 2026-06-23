Write-Host "=== eBay Draft Commander - Unregister Background Service ===" -ForegroundColor Cyan

# 1. Stop and Unregister Backend Task
$backendTask = Get-ScheduledTask -TaskName "eBayDraftCommanderBackend" -ErrorAction SilentlyContinue
if ($backendTask) {
    Write-Host "[...] Stopping and removing eBayDraftCommanderBackend task" -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName "eBayDraftCommanderBackend" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "eBayDraftCommanderBackend" -Confirm:$false | Out-Null
    Write-Host "[OK] Removed eBayDraftCommanderBackend task" -ForegroundColor Green
} else {
    Write-Host "[INFO] eBayDraftCommanderBackend task is not registered" -ForegroundColor DarkGray
}

# 2. Stop and Unregister Caddy Task
$caddyTask = Get-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -ErrorAction SilentlyContinue
if ($caddyTask) {
    Write-Host "[...] Stopping and removing eBayDraftCommanderCaddy task" -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "eBayDraftCommanderCaddy" -Confirm:$false | Out-Null
    Write-Host "[OK] Removed eBayDraftCommanderCaddy task" -ForegroundColor Green
} else {
    Write-Host "[INFO] eBayDraftCommanderCaddy task is not registered" -ForegroundColor DarkGray
}

# 3. Clean up Startup folder shortcuts
$startupFolder = [Environment]::GetFolderPath("Startup")
$backendShortcutPath = Join-Path $startupFolder "eBay Draft Commander Backend.lnk"
$caddyShortcutPath = Join-Path $startupFolder "eBay Draft Commander Caddy.lnk"

if (Test-Path $backendShortcutPath) {
    Write-Host "[...] Removing Backend Startup Shortcut" -ForegroundColor Yellow
    Remove-Item $backendShortcutPath -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed Backend Startup Shortcut" -ForegroundColor Green
}
if (Test-Path $caddyShortcutPath) {
    Write-Host "[...] Removing Caddy Startup Shortcut" -ForegroundColor Yellow
    Remove-Item $caddyShortcutPath -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed Caddy Startup Shortcut" -ForegroundColor Green
}

# 4. Clean up running processes just in case
Write-Host "[...] Checking for orphaned python/caddy processes on service port..." -ForegroundColor Yellow
try {
    # Find process ID running on port 5000
    $netstat = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
    if ($netstat) {
        $owningPid = $netstat.OwningProcess
        Write-Host "Stopping process ID $owningPid listening on port 5000..." -ForegroundColor Yellow
        Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Stopped port 5000 process" -ForegroundColor Green
    }
} catch {
    Write-Host "[WARNING] Failed to query or stop process on port 5000: $_" -ForegroundColor Yellow
}

# Kill caddy if it is running
$caddyProc = Get-Process -Name "caddy" -ErrorAction SilentlyContinue
if ($caddyProc) {
    Write-Host "Stopping running Caddy process..." -ForegroundColor Yellow
    Stop-Process -Name "caddy" -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Stopped Caddy process" -ForegroundColor Green
}

Write-Host "`nAll background tasks unregistered successfully." -ForegroundColor Green
