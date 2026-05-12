@echo off
title AERO - Startup
cd /d "%~dp0"

echo.
echo  ==========================================
echo   AERO - Automated Evaluation Of Resource
echo          Occupancy  (FedEx P^&E)
echo  ==========================================
echo.

:: If .venv already exists jump straight to launch
if exist ".venv\Scripts\python.exe" goto launch

:: Find Python -- try 'python' then Windows 'py' launcher
set PYTHON=
python --version >nul 2>&1
if not errorlevel 1 set PYTHON=python

if "%PYTHON%"==" " goto try_py
if "%PYTHON%"=="" goto try_py
goto got_python

:try_py
py --version >nul 2>&1
if not errorlevel 1 set PYTHON=py

:got_python
if "%PYTHON%"=="" (
    echo  [ERROR] Python not found on PATH.
    echo  1. Install Python 3.10+ from https://python.org
    echo     Tick "Add Python to PATH" during install.
    echo  2. Or use PowerShell directly:
    echo     .venv\Scripts\python.exe -m streamlit run main.py
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('%PYTHON% --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% found.

echo  Creating virtual environment...
%PYTHON% -m venv .venv
if errorlevel 1 ( echo  [ERROR] venv failed. & pause & exit /b 1 )

echo  Installing dependencies (first run ~1 minute)...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe _filter_reqs.py
.venv\Scripts\python.exe -m pip install -r _req_tmp.txt --quiet
if exist _req_tmp.txt del _req_tmp.txt
echo  Done.
echo.

:launch
echo  Seeding users...
.venv\Scripts\python.exe setup_users.py >nul 2>&1
echo  Starting AERO at http://localhost:8501
echo  Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe -m streamlit run main.py --server.headless false --browser.gatherUsageStats false
