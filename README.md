# AERO — Automated Evaluation of Resource Occupancy

Enterprise-grade FedEx India field-engineering analytics and planning platform built with Python + Streamlit.

---

## Overview

AERO provides role-separated operational tooling for FedEx Planning & Engineering:

| Role | What they see |
|------|--------------|
| **Field (Facility)** | Data Upload Centre · Station & Hub Planning · Station Analytics |
| **Gateway** | Gateway Operations |
| **Services** | Services Operations (Delay Prediction Engine) |
| **Leadership** | Executive Dashboard (NSL Analytics, Station/Hub health) |
| **Operations** | All modules |

---

## Quick Start

```bat
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (copy and edit)
copy .env .env.local      # or edit .env directly

# 4. Run
.venv\Scripts\streamlit run main.py
```

Default admin credentials (set in `.env`):

| User | Password | Role |
|------|----------|------|
| `admin` | `Admin@123456` | Operations |
| `facility_mgr` | `Facility@2024` | Facility |
| `gateway_coord` | `Gateway@2024` | Gateway |
| `services_lead` | `Services@2024` | Services |
| `executive` | `Leadership@2024` | Leadership |

---

## Field Engineer Workflow

### Step 1 — Upload Data (`Data Upload Centre`)
- Drop FAMIS REPORT `.xlsx` files (weekly/daily/monthly) into the uploader.
- Upload the Facility Master `.xlsx` file with station capacity baselines.
- Both files are **automatically upserted** to PostgreSQL and archived locally in `docs/`.
- No manual "Publish" button required.

### Step 2 — Plan (`Station Planning`)
Three tabbed planning tools, all auto-populated from uploaded FAMIS data:

| Tab | Purpose |
|-----|---------|
| **Area Planning** | Sorting area, caging, equipment and aisle space from volume |
| **Resource Planning** | OSA / LASA / Dispatcher / Trace Agent headcount via TACT |
| **Courier Planning** | Courier headcount from stops, productivity and absenteeism |

### Step 3 — Monitor (`Station Analytics`)
- **Regional overview** — KPI cards: total stations, healthy %, critical alerts, network volume.
- **Station status grid** — per-station AREA / RESOURCE / COURIER status cards colour-coded green/amber/red.
- **Station drill-down** — click any station to see historical volume, area utilisation, agent and courier requirement trends with Plotly charts.
- **Network volume trend** — last 30-day network-wide volume chart.

---

## Architecture

```
main.py                  — App entry point, role-based routing
pages/
  home.py                — Role-specific landing pages
  field_upload.py        — Data Upload Centre (FAMIS + Master)
  station_planner.py     — Station Planning Suite (Area / Resource / Courier)
  station_analytics.py   — Station Health Analytics & Drill-Down
  hub_planner.py         — Hub Planning Suite
  gateway_ops.py         — Gateway Operations (Phase 2)
  services_ops.py        — Services Operations (Delay Predictor)
  leadership_dashboard.py— Executive Dashboard (NSL Analytics)
  admin_controls.py      — System Configuration
  health_monitor.py      — Health Monitor renderer (used by hub page)
  area_planner.py        — Area planning renderer
  resource_planner.py    — Resource planning renderer
  courier_planner.py     — Courier planning renderer

aero/
  auth/service.py        — RBAC: bcrypt auth, role validation, user management
  core/
    area_calculator.py   — Area requirement calculations
    resource_calculator.py— OSA/LASA/Dispatcher/Trace calculations
    courier_calculator.py — Courier headcount calculations
    health.py            — Shared health-status logic
  data/
    famis_store.py       — PostgreSQL FAMIS persistence layer
    nsl_store.py         — PostgreSQL NSL analytics persistence
    excel_store.py       — Excel fallback persistence (FAMIS_UPLOADED_FILES.xlsx)
    hub_store.py         — Hub-scoped Excel persistence
    inbox_loader.py      — Inbox folder auto-scan (aero/data/inbox/)
    station_store.py     — Station master workbook CRUD
    postgres.py          — PostgreSQL connection pool (psycopg2)
  db/schema.sql          — PostgreSQL schema (upload_history, station_health,
                           nsl_shipments, nsl_upload_log, famis_data, famis_upload_log)
  config/settings.py     — TACT / area config (tact.json, area.json), 5-min cache
  ui/
    components.py        — Reusable FedEx-branded UI elements
    header.py            — Top bar (logo, title, user badge)
    sidebar.py           — Sidebar animation CSS
    styles.py            — Global CSS variables and brand colours
    session.py           — Session state initialisation
    nsl_tab.py           — NSL analytics tab renderer
```

---

## Data Persistence

| Data | Primary Store | Fallback |
|------|--------------|---------|
| FAMIS volume data | PostgreSQL `famis_data` | `data/FAMIS_UPLOADED_FILES.xlsx` |
| Health reports | PostgreSQL `station_health` | `data/FAMIS_REPORT_DATA.xlsx` |
| NSL shipments | PostgreSQL `nsl_shipments` | Local pickle cache `_nsl_cache.pkl` |
| MD Scorecard | Local pickle `_scorecard_cache.pkl` | — |
| File archives | `docs/famis/` · `docs/master/` | — |
| Inbox auto-load | `aero/data/inbox/{famis,nsl,scorecard}/` | — |

---

## PostgreSQL Setup (Optional — Enables Full Analytics)

```bat
REM 1. Install PostgreSQL 16+ from https://www.postgresql.org/download/windows
REM 2. Create database
"C:\Program Files\PostgreSQL\16\bin\psql" -U postgres -c "CREATE DATABASE aero_planner;"
REM 3. Apply schema
"C:\Program Files\PostgreSQL\16\bin\psql" -U postgres -d aero_planner -f aero\db\schema.sql
REM 4. Restart app — auto-detects DB and switches from Excel to PostgreSQL mode
```

`.env` is pre-configured for `localhost:5432 / aero_planner / postgres`. Change `POSTGRES_PASSWORD` to match your installation.

---

## Security

- **Authentication**: bcrypt (work factor 12) with auto-upgrade from legacy SHA-256
- **RBAC**: Strict role-based page routing — each role sees only its own modules
- **Formula injection prevention** (SEC-006): Excel cell values prefixed if they start with `=+-@|%`
- **Path traversal prevention** (SEC-007): All file paths validated against `DATA_DIR` / `PROJECT_ROOT`
- **Atomic writes** (DL-008): Temp file + `os.replace()` — no corrupt workbooks on crash
- **Connection pooling**: `ThreadedConnectionPool(min=1, max=5)` for PostgreSQL

---

## Inbox Auto-Load

Drop files into these folders and restart the app — data is auto-ingested:

```
aero/data/inbox/
  famis/       ← FAMIS REPORT_WE_*.xlsx
  nsl/         ← IN Outbound/Inbound *.txt / *.csv
  scorecard/   ← MD Scorecard *.xlsb
  processed/   ← auto-moved after ingestion
```

---

## Configuration

Edit via **System Configuration** in the app or directly:

| File | Contents |
|------|---------|
| `aero/config/tact.json` | OSA / LASA / Dispatcher / Trace Agent TACT values (minutes) |
| `aero/config/area.json` | Area constants: pallet area, aisle %, sorting %, cage % |
| `.env` | DB connection, seed users, app settings |
