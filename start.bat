@echo off
title Automa - AI Content Intelligence Platform
cd /d "%~dp0"

echo ============================================================
echo        AUTOMA: AI MULTI-AGENT CONTENT PLATFORM
echo ============================================================
echo.
echo Select an action:
echo.
echo   [1] Launch Web Dashboard (auto-opens browser)
echo   [2] Run Multi-Agent Research ^& Content Pipeline Now
echo   [3] Publish Queued Posts to LinkedIn / X Now
echo   [4] View Live Platform ^& Intelligence Status
echo   [5] Start 24/7 Continuous Background Scheduler
echo   [6] Exit
echo.
set /p choice="Enter choice [1-6] (Press Enter for Dashboard): "
if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    echo.
    echo Starting Web Dashboard at http://localhost:8000 ...
    start http://localhost:8000
    .\.venv\Scripts\python.exe -m automa.cli web --port 8000
    goto finish
)

if "%choice%"=="2" (
    echo.
    echo Running Multi-Agent Pipeline (Discovery -^> Verification -^> Ranking -^> Copywriting)...
    .\.venv\Scripts\python.exe -m automa.cli pipeline
    echo.
    pause
    goto finish
)

if "%choice%"=="3" (
    echo.
    echo Publishing scheduled posts to LinkedIn / X...
    .\.venv\Scripts\python.exe -m automa.cli publish --force
    echo.
    pause
    goto finish
)

if "%choice%"=="4" (
    echo.
    .\.venv\Scripts\python.exe -m automa.cli status
    echo.
    pause
    goto finish
)

if "%choice%"=="5" (
    echo.
    echo Starting 24/7 continuous scheduler daemon...
    .\.venv\Scripts\python.exe -m automa.cli start
    goto finish
)

:finish
