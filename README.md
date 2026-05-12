# AERO — Automated Evaluation Of Resource Occupancy

FedEx Planning & Engineering | Internal Operations Platform

---

## Quick Start

### Option 1 — PowerShell (recommended, always works)

```powershell
cd C:\Users\NEW\Documents\Aero-MAIN

# First time only: create venv and install deps
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe setup_users.py

# Every time to start the app
.venv\Scripts\python.exe -m streamlit run main.py
```

App opens at **http://localhost:8501**

---

### Option 2 — Double-click `start_aero.bat`

Handles venv creation and dependency install automatically on first run.
If Python is not found, use Option 1 (PowerShell) instead.

> **Note:** If you see `python not found` in the bat file, your Python
> is installed but not on the system PATH for CMD. PowerShell Option 1
> will always work regardless of PATH configuration.

---

## Login Credentials

| Role | User ID | Password |
|---|---|---|
| **Operations** (all access) | `admin` | `Admin@123456` |
| **Facility** | `facility_mgr` | `Facility@2024` |
| **Gateway** | `gateway_coord` | `Gateway@2024` |
| **Services** | `services_lead` | `Services@2024` |
| **Leadership** | `executive` | `Leadership@2024` |
---

## Project Structure

```
Aero-MAIN/
|-- main.py                  # App entry point, role-based routing
|-- start_aero.bat           # Windows one-click launcher
|-- requirements.txt         # Python dependencies
|-- setup_users.py           # Seeds default user accounts
|
|-- pages/
|   |-- home.py              # Role-aware landing page
|   |-- login.py             # Split-screen login
|   |-- health_monitor.py    # Station health monitoring
|   |-- hub_health_monitor.py
|   |-- station_planner.py   # Area / Resource / Courier planners
|   |-- hub_planner.py
|   |-- services_ops.py      # Delay prediction engine (NSL + AWB)
|   |-- leadership_dashboard.py
|   |-- gateway_ops.py       # Phase 2 placeholder
|   `-- admin_controls.py
|
|-- aero/
|   |-- core/
|   |   |-- delay_predictor.py   # Bayesian NSL risk model
|   |   |-- area_calculator.py
|   |   |-- resource_calculator.py
|   |   `-- courier_calculator.py
|   |-- data/
|   |   |-- nsl_store.py     # NSL parsing + model/prediction storage
|   |   |-- excel_store.py
|   |   `-- postgres.py      # Optional (app runs without it)
|   |-- ui/
|   |   |-- styles.py        # Global CSS design tokens (FedEx brand)
|   |   |-- header.py        # Topbar + user badge
|   |   |-- components.py    # Shared components (KPI cards, banners, etc.)
|   |   `-- session.py       # Session state initialisation
|   `-- auth/
|       `-- service.py       # bcrypt auth, role management
|
|-- data/                    # Runtime data (model JSON, prediction Excel)
|-- assets/                  # FedEx logo, brand font
`-- tests/                   # Unit tests
```

---

## Roles & Access

| Role | Pages |
|---|---|
| **Facility** | Home, Station Planner (Area/Resource/Courier), Hub Planner, Health Monitor, Admin |
| **Services** | Home, Services Operations (Delay Prediction) |
| **Gateway** | Home, Gateway Operations |
| **Leadership** | Home, Executive Dashboard |
| **Operations** | All of the above |

---

## Services Module — Delay Prediction Engine

1. Log in as `services_user`
2. Go to **Services Operations → Training Data**
3. Upload the NSL historical file (tab-separated `.txt`, `.csv`, or `.xlsx`)
   - Required columns: `orig_loc_cd`, `dest_loc_cd`, `NSL_OT_VOL`
4. Click **Train Model** — model persists across sessions
5. Go to **Daily Prediction**, upload today's AWB file
6. Click **Run Prediction** — results show Critical / High Risk / At Risk / Passing

---

## Dependencies

Python 3.10+ required. Key packages:

- `streamlit` — web UI framework
- `pandas`, `openpyxl` — data processing and Excel I/O
- `plotly` — charts
- `bcrypt` — password hashing
- `python-dotenv` — environment variables
- `psycopg2-binary` *(optional)* — PostgreSQL; app runs in Excel-only mode without it

---

## Branch

Active development branch: **`akshat-vora`**
