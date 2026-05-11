# AERO — Automated Evaluation of Resource Occupancy

**FedEx Facility Planning & Health Monitoring Platform**

AERO is a Streamlit-based internal tool for FedEx operations that automates resource occupancy evaluation. It ingests FAMIS volume data to calculate staffing requirements, operational area needs, and courier capacity across multiple facility types.

---

## Architecture

```
main.py                  — App entry point: auth gate, navigation, session init
pages/                   — Streamlit multi-page app (one file per page)
aero/
  auth/service.py        — bcrypt-based authentication against Excel credential store
  config/settings.py     — TACT & area configuration (JSON-backed, cached)
  core/                  — Pure business logic: area, resource, courier, health calculators
  data/
    excel_store.py       — FAMIS upload & report persistence (Excel)
    station_store.py     — Per-station planner workbook CRUD (Excel)
    postgres.py          — PostgreSQL health-data persistence (pooled connections)
  db/schema.sql          — PostgreSQL schema with CHECK constraints and FK
  ui/                    — Shared UI components: styles, sidebar, header, session state
assets/                  — Static assets (logo, fonts)
data/                    — Runtime data directory (gitignored — xlsx files created here)
tests/                   — pytest unit tests for all aero/core/ and security functions
```

### Dual Storage Strategy

| Store | Purpose | Format |
|---|---|---|
| Excel (`data/*.xlsx`) | Transient planning data; per-station Area / Resource / Courier inputs | openpyxl |
| PostgreSQL (`station_health`) | Persistent health-monitor summaries; queryable across uploads | psycopg2 pool |

The two stores are intentionally independent — Excel holds live planning state while PostgreSQL holds time-series health snapshots. No automatic synchronization is performed.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (optional — app runs in Excel-only mode if DB is unavailable)
- Git

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/Shubzzz10/AERO.git
cd AERO
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in real values:

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_HOST` | No | DB host (default: `localhost`) |
| `POSTGRES_PORT` | No | DB port (default: `5432`) |
| `POSTGRES_DB` | No | DB name (default: `aero_planner`) |
| `POSTGRES_USER` | No | DB user (default: `postgres`) |
| `POSTGRES_PASSWORD` | **Yes** | DB password — no default, must be set |
| `AERO_SEED_USER_<N>_ID` | First run | Login ID for user slot N (1–10) |
| `AERO_SEED_USER_<N>_PASS` | First run | Password for user slot N (plain, hashed on write) |
| `AERO_SEED_USER_<N>_ROLE` | First run | Role: `Facility`, `Gateway`, `Services`, `Leadership` |
| `AERO_SEED_USER_<N>_NAME` | No | Display name for user slot N |

> **Important:** `.env` is gitignored and must never be committed. All credentials live in `.env` only.

### 3. Set up the PostgreSQL database (if using DB features)

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE aero_planner;"

# Schema is applied automatically by the app on first use.
# To apply manually:
psql -U postgres -d aero_planner -f aero/db/schema.sql
```

### 4. First-run user seeding

On first startup, if `data/AERO_USERS.xlsx` does not exist, the app reads `AERO_SEED_USER_*` env vars to create it. Passwords are hashed with bcrypt (work factor 12) and the plaintext is never stored.

If no seed vars are set, `AERO_USERS.xlsx` must be created manually with columns: `user_id`, `display_name`, `role`, `password_hash`, `is_active`.

### 5. Run the application

```bash
streamlit run main.py
```

---

## Running Tests

```bash
# From the project root, with the venv activated:
pip install pytest
pytest tests/ -v
```

Test files:

| File | Coverage |
|---|---|
| `tests/test_health.py` | `aero.core.health` — all branches of `calculate_health_status`, `get_summary_stats` |
| `tests/test_area_calculator.py` | `aero.core.area_calculator` — facility models A/B/C/D, area health status |
| `tests/test_resource_calculator.py` | `aero.core.resource_calculator` — OSA, LASA, Dispatcher, Trace Agent |
| `tests/test_security.py` | Formula injection sanitizer, path traversal guard, bcrypt hashing |

---

## Security Notes

| Finding | Remediation |
|---|---|
| SEC-001: No plaintext credentials in source | First-run seeding reads from `.env` vars only |
| SEC-003: bcrypt hashing | `_hash_password()` uses `bcrypt.hashpw` with gensalt; SHA-256 hashes auto-upgrade on login |
| SEC-004: No empty DB password | `POSTGRES_PASSWORD` has no default; app raises `RuntimeError` if unset |
| SEC-006: Formula injection | All Excel writes pass through `_sanitize_cell()` / `_sanitize_df()` |
| SEC-007: Path traversal | `_safe_path()` in `station_store.py` validates all paths against `DATA_DIR` |
| SEC-011: XSRF protection | `.streamlit/config.toml` sets `enableXsrfProtection = true`, `enableCORS = false` |

For production deployments, add a reverse proxy (nginx/Caddy) that sets:
- `Content-Security-Policy`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security`

---

## Configuration

TACT values (time-allocation coefficients) and area constants are managed via the **Admin Configuration** page (Facility role only) and are persisted to:

- `aero/config/tact.json` — OSA, LASA, Dispatcher, Trace Agent, Courier TACT values
- `aero/config/area.json` — Area planner constants (pallet area, aisle %, cage %, etc.)

Both files are loaded with a 5-minute in-memory cache (`@st.cache_data(ttl=300)`) and the cache is invalidated automatically whenever a config save occurs.

---

## Role-Based Access

| Role | Pages |
|---|---|
| Facility | Home, Station Planner, Hub Planner, Admin Configuration |
| Gateway | Home, Gateway Operations |
| Services | Home, Services Operations |
| Leadership | Home, Executive Dashboard |

---

## Deployment Notes

1. Set all required `.env` variables in your hosting environment (never commit `.env`)
2. Ensure `data/` is a persistent volume (not ephemeral)
3. Set `POSTGRES_PASSWORD` as a secret in your deployment platform
4. Point Streamlit's `server.port` and `server.baseUrlPath` appropriately
5. Add a reverse proxy with TLS termination and security headers
