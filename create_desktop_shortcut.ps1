$ErrorActionPreference = "Stop"

$SCRIPT_DIR = $PSScriptRoot
$TARGET_PATH = Join-Path -Path $SCRIPT_DIR -ChildPath "launch_app.bat"
$SHORTCUT_PATH = Join-Path -Path ([Environment]::GetFolderPath("Desktop")) -ChildPath "eBay Draft Commander.lnk"
$ICON_PATH = Join-Path -Path $SCRIPT_DIR -ChildPath "static\favicon.ico"

# Check if specific icon exists, otherwise fall back to default or generic
if (-not (Test-Path $ICON_PATH)) {
    # Try looking in other common places or just don't set a specific icon (windows default)
    $ICON_PATH = "" 
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($SHORTCUT_PATH)
$Shortcut.TargetPath = $TARGET_PATH
$Shortcut.WorkingDirectory = $SCRIPT_DIR
$Shortcut.WindowStyle = 7 # Minimized (optional, but maybe better to see the console for errors? Let's leave default or normal)
$Shortcut.WindowStyle = 1 # Normal window
$Shortcut.Description = "Launch eBay Draft Commander"

if ($ICON_PATH -ne "") {
    $Shortcut.IconLocation = $ICON_PATH
}

$Shortcut.Save()

Write-Host "Successfully created desktop shortcut: $SHORTCUT_PATH"
