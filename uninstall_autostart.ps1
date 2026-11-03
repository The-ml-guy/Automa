# ==============================================================================
# AUTOMA AUTOSTART UNINSTALLER
# ==============================================================================

$StartupFolder = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupFolder "AutomaBackground.lnk"

if (Test-Path $ShortcutPath) {
    Remove-Item $ShortcutPath -Force
    Write-Host "Automa auto-start removed successfully." -ForegroundColor Yellow
} else {
    Write-Host "Automa was not registered in Startup." -ForegroundColor Gray
}

