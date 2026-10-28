# ==============================================================================
# AUTOMA — WINDOWS TASK SCHEDULER REGISTRATION SCRIPT
# ==============================================================================
# Run this script in PowerShell as Administrator to run Automa permanently in the background,
# completely independent of the Antigravity IDE.
# ==============================================================================

$TaskName = "AutomaBackgroundPublishingService"
$Action = New-ScheduledTaskAction `
    -Execute "F:\automa\.venv\Scripts\python.exe" `
    -Argument "-m automa.cli daemon" `
    -WorkingDirectory "F:\automa"

$Trigger = New-ScheduledTaskTrigger -AtLogon
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Register the Scheduled Task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Automa Autonomous Social Media Publishing Background Runner" `
    -Force

Write-Host "Automa persistent task registered successfully." -ForegroundColor Green
Write-Host "To start the task immediately:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
Write-Host "To check status:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
Write-Host "To unregister later:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:$false" -ForegroundColor Yellow
