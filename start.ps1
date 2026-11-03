# Automa 1-Click Interactive Launcher
Set-Location -Path $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "        AUTOMA: AI MULTI-AGENT CONTENT PLATFORM" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Select an action:" -ForegroundColor Yellow
Write-Host "  [1] Launch Web Dashboard (auto-opens browser)"
Write-Host "  [2] Run Multi-Agent Research & Content Pipeline Now"
Write-Host "  [3] Publish Queued Posts to LinkedIn / X Now"
Write-Host "  [4] View Live Platform & Intelligence Status"
Write-Host "  [5] Start 24/7 Continuous Background Scheduler"
Write-Host "  [6] Exit"
Write-Host ""

$choice = Read-Host "Enter choice [1-6] (Default is 1)"
if ([string]::IsNullOrWhiteSpace($choice)) {
    $choice = "1"
}

switch ($choice) {
    "1" {
        Write-Host "`nStarting Web Dashboard at http://localhost:8000 ..." -ForegroundColor Green
        Start-Process "http://localhost:8000"
        & $python -m automa.cli web --port 8000
    }
    "2" {
        Write-Host "`nRunning Multi-Agent Intelligence Pipeline..." -ForegroundColor Green
        & $python -m automa.cli pipeline
        Write-Host "`nDone." -ForegroundColor Green
    }
    "3" {
        Write-Host "`nPublishing scheduled posts to LinkedIn / X..." -ForegroundColor Green
        & $python -m automa.cli publish --force
        Write-Host "`nDone." -ForegroundColor Green
    }
    "4" {
        & $python -m automa.cli status
    }
    "5" {
        Write-Host "`nStarting 24/7 background scheduler..." -ForegroundColor Green
        & $python -m automa.cli start
    }
    Default {
        Write-Host "Exiting." -ForegroundColor Gray
    }
}
