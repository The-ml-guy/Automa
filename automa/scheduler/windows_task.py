"""
Windows Scheduled Task Automation Script Generator for Automa (Phase 7 & 11).
Generates ready-to-run PowerShell scripts to register Automa as a persistent Windows background job.
"""

from __future__ import annotations
import sys
from pathlib import Path
from automa.config import BASE_DIR


def generate_powershell_registration_script() -> str:
    """Generates a PowerShell script to register Automa with Windows Task Scheduler."""
    python_exe = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    runner_script = BASE_DIR / "automa" / "cli.py"

    ps_script = f"""# ==============================================================================
# AUTOMA — WINDOWS TASK SCHEDULER REGISTRATION SCRIPT
# ==============================================================================
# Run this script in PowerShell as Administrator to run Automa permanently in the background,
# completely independent of the Antigravity IDE.
# ==============================================================================

$TaskName = "AutomaBackgroundPublishingService"
$Action = New-ScheduledTaskAction `
    -Execute "{python_exe}" `
    -Argument "-m automa.cli daemon" `
    -WorkingDirectory "{BASE_DIR}"

$Trigger = New-ScheduledTaskTrigger -AtLogon
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\\$env:USERNAME" -LogonType Interactive -RunLevel Highest
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
"""
    return ps_script


def export_registration_script() -> Path:
    """Writes register_windows_task.ps1 to project root."""
    target_path = BASE_DIR / "register_windows_task.ps1"
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(generate_powershell_registration_script())
    return target_path
