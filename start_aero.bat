@echo off
title AERO — Startup
cd /d "%~dp0"

echo.
echo  ==========================================
echo   AERO — Automated Evaluation Of Resource
echo           Occupancy (FedEx P^&E)
echo  ==========================================
echo.

:: ── Check Python ────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found on PATH.
    echo  Install Python 3.10+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% detected.

:: ── Create venv if missing ───────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo  Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  Virtual environment created.

    echo  Installing dependencies (this takes ~1 min on first run)...
    .venv\Scripts\python.exe -m pip install --upgrade pip --quiet

    :: Filter out psycopg2 — no pre-built wheel for Python 3.11+
    .venv\Scripts\python.exe -c ^
      "lines=[l for l in open('requirements.txt') if 'psycopg2' not in l.lower()]; open('_req_tmp.txt','w').writelines(lines)"
    .venv\Scripts\pip.exe install -r _req_tmp.txt --quiet
    del _req_tmp.txt

    echo  Dependencies installed.
    echo.
)

:: ── Seed users (safe to re-run) ─────────────────────────────
echo  Seeding default users...
.venv\Scripts\python.exe setup_users.py >nul 2>&1

:: ── Launch ───────────────────────────────────────────────────
echo  Starting AERO on http://localhost:8501
echo  Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe -m streamlit run main.py --server.headless false --browser.gatherUsageStats false
