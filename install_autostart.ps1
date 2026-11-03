# ==============================================================================
# AUTOMA AUTOSTART INSTALLER FOR WINDOWS
# Adds Automa to Windows Startup so it runs silently on boot / laptop logon
# ==============================================================================

$StartupFolder = [Environment]::GetFolderPath('Startup')
$VbsPath = "F:\automa\automa_background.vbs"
$ShortcutPath = Join-Path $StartupFolder "AutomaBackground.lnk"

Write-Host "Installing Automa Autostart..." -ForegroundColor Cyan

if (-not (Test-Path $VbsPath)) {
    Write-Error "Could not find $VbsPath"
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$VbsPath`""
$Shortcut.WorkingDirectory = "F:\automa"
$Shortcut.Description = "Automa Social Media AI Automation Background Service"
$Shortcut.Save()

if (Test-Path $ShortcutPath) {
    Write-Host "Success! Automa is now configured to auto-start on laptop login." -ForegroundColor Green
    Write-Host "Location: $ShortcutPath" -ForegroundColor Gray
} else {
    Write-Error "Failed to create startup shortcut."
}

