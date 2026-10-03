<#
.SYNOPSIS
    Builds and optionally installs the eBay Draft Commander Android Wrapper app.

.DESCRIPTION
    Compiles the native Android wrapper APK using Gradle and the local Android SDK.
    Supports installing to a connected Android phone or emulator via ADB.

.PARAMETER Release
    Build a release APK instead of debug.

.PARAMETER Install
    Automatically install the built APK to a connected device via ADB.

.PARAMETER Run
    Launch the app on the connected device after installation.

.EXAMPLE
    .\scripts\build-android.ps1
    .\scripts\build-android.ps1 -Install -Run
    .\scripts\build-android.ps1 -Release
#>

param(
    [switch]$Release,
    [switch]$Install,
    [switch]$Run
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AndroidDir = Join-Path $RepoRoot "android"
$Gradlew = Join-Path $AndroidDir "gradlew.bat"

if (-not (Test-Path $Gradlew)) {
    Write-Error "Gradle wrapper not found at $Gradlew"
    exit 1
}

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  eBay Draft Commander — Android Build Tool  " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$Task = if ($Release) { "assembleRelease" } else { "assembleDebug" }
$ApkSubdir = if ($Release) { "release" } else { "debug" }
$ApkName = if ($Release) { "app-release-unsigned.apk" } else { "app-debug.apk" }

Write-Host "`n[1/3] Building APK with Gradle ($Task)..." -ForegroundColor Yellow

Push-Location $AndroidDir
try {
    & cmd /c $Gradlew $Task
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Gradle build failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

$ApkPath = Join-Path $AndroidDir "app\build\outputs\apk\$ApkSubdir\$ApkName"
if (-not (Test-Path $ApkPath)) {
    # Check for any generated .apk in that directory
    $Candidates = Get-ChildItem (Join-Path $AndroidDir "app\build\outputs\apk\$ApkSubdir") -Filter *.apk
    if ($Candidates.Count -gt 0) {
        $ApkPath = $Candidates[0].FullName
    } else {
        Write-Error "Could not locate generated APK in app\build\outputs\apk\$ApkSubdir"
        exit 1
    }
}

$ApkSizeMb = [math]::Round(((Get-Item $ApkPath).Length / 1MB), 2)
Write-Host "`n[2/3] Build succeeded!" -ForegroundColor Green
Write-Host "  APK:  $ApkPath" -ForegroundColor White
Write-Host "  Size: $ApkSizeMb MB" -ForegroundColor White

if ($Install -or $Run) {
    Write-Host "`n[3/3] Checking ADB devices..." -ForegroundColor Yellow
    $AdbDevicesOutput = adb devices
    $Devices = @()
    $AdbDevicesOutput -split "`r?`n" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not ($line -match "^List of devices") -and ($line -match "\s+device$")) {
            $Devices += ($line -split "\s+")[0]
        }
    }

    if ($Devices.Count -eq 0) {
        Write-Warning "No connected Android devices or emulators found via ADB."
        Write-Host "To install manually on your phone:"
        Write-Host "  1. Transfer '$ApkPath' to your device or run 'adb connect <phone-ip>'."
        Write-Host "  2. Or start an emulator with 'android emulator start medium_phone' and run this script with -Install."
        exit 0
    }

    $TargetDevice = $Devices[0]
    Write-Host "Installing to device: $TargetDevice..." -ForegroundColor Cyan
    adb -s $TargetDevice install -r $ApkPath

    if ($LASTEXITCODE -ne 0) {
        Write-Error "ADB install failed"
        exit $LASTEXITCODE
    }
    Write-Host "Successfully installed!" -ForegroundColor Green

    if ($Run) {
        $Package = if ($Release) { "com.ebaydraftcommander.app" } else { "com.ebaydraftcommander.app.debug" }
        $Activity = "com.ebaydraftcommander.app.MainActivity"
        Write-Host "Launching $Package/$Activity..." -ForegroundColor Cyan
        adb -s $TargetDevice shell am start -n "$Package/$Activity"
    }
} else {
    Write-Host "`nTo install on a device, run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\build-android.ps1 -Install -Run" -ForegroundColor White
}
