@echo off
title AERO - Startup
cd /d "%~dp0"

echo.
echo  ==========================================
echo   AERO - Automated Evaluation Of Resource
echo          Occupancy  (FedEx P^&E)
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found on PATH.
    echo  Install Python 3.10+ from https://python.org
    echo  Tick "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% detected.

:: Create virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo  Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  Installing dependencies ^(first run ~1 min^)...
    .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    .venv\Scripts\python.exe _filter_reqs.py
    .venv\Scripts\pip.exe install -r _req_tmp.txt --quiet
    if exist _req_tmp.txt del _req_tmp.txt
    echo  Done.
    echo.
)

:: Seed default users
echo  Seeding users...
.venv\Scripts\python.exe setup_users.py >nul 2>&1

:: Launch
echo  Starting AERO at http://localhost:8501
echo  Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe -m streamlit run main.py --server.headless false --browser.gatherUsageStats false
