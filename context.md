# AERO — Project Context Reference

**Automated Evaluation of Resource Occupancy**  
FedEx Facility Planning Platform — Streamlit Multi-Page Application

---

## 1. Project Overview

AERO is an internal Streamlit web application for FedEx facility operations teams. It provides role-based access to health monitoring, area planning, resource staffing, and courier planning tools across Stations and Hubs.

### Purpose
- Automate FAMIS (data) ingestion and health scoring for stations and hubs
- Calculate area, resource, and courier requirements from business formulas
- Provide Leadership with a consolidated eagle's-eye analytics view
- Enable Operations teams to access both division tools in one login

---

## 2. Project Structure

```
AERO-main/
├── main.py                          # App entry point — routing, auth gate, navigation
├── requirements.txt                 # Python dependencies
├── README.md                        # Project readme
│
├── aero/                            # Core application package
│   ├── __init__.py                  # DATA_DIR, ASSETS_DIR constants
│   ├── auth/
│   │   ├── __init__.py
│   │   └── service.py               # Bcrypt auth, VALID_ROLES, seed_users()
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # load_config(), load_area_config()
│   │   ├── tact.json                # TACT standards (task times)
│   │   └── area.json                # Area calculator constants
│   ├── core/
│   │   ├── __init__.py
│   │   ├── area_calculator.py       # calculate_area_requirements(), PREDEFINED_AREAS
│   │   ├── resource_calculator.py   # calculate_resource_requirements()
│   │   ├── courier_calculator.py    # calculate_courier_requirements()
│   │   └── health.py                # score_area_health(), score_resource_health(), etc.
│   ├── data/
│   │   ├── __init__.py
│   │   ├── excel_store.py           # Station FAMIS persistence (FAMIS_*.xlsx)
│   │   ├── hub_store.py             # Hub FAMIS persistence (HUB_*.xlsx) [NEW]
│   │   ├── postgres.py              # (unused — reserved for future DB migration)
│   │   └── station_store.py         # Station master data reader
│   ├── db/
│   │   └── schema.sql               # Reserved DB schema
│   └── ui/
│       ├── __init__.py
│       ├── components.py            # Reusable UI components (cards, charts, banners)
│       ├── header.py                # render_header(), render_footer()
│       ├── session.py               # init_session_state() — all default keys
│       ├── sidebar.py               # render_sidebar()
│       └── styles.py                # apply_styles() — CSS variables + FedEx brand font
│
├── pages/                           # Streamlit pages (one file = one page)
│   ├── __init__.py
│   ├── login.py                     # Sign-in page
│   ├── home.py                      # Home/landing page (all roles)
│   ├── admin_controls.py            # Configuration (Facility + Operations roles)
│   ├── station_planner.py           # Station 4-tab container
│   ├── health_monitor.py            # Station health monitor (AREA/RESOURCE/COURIER/ANALYTICS)
│   ├── area_planner.py              # Station area tracker
│   ├── resource_planner.py          # Station resource tracker (OSA, LASA, Dispatcher, Trace)
│   ├── courier_planner.py           # Station courier tracker
│   ├── hub_planner.py               # Hub 4-tab container [UPDATED]
│   ├── hub_health_monitor.py        # Hub health monitor [NEW]
│   ├── hub_area_planner.py          # Hub area tracker [NEW]
│   ├── hub_resource_planner.py      # Hub resource tracker (bridges to station) [NEW]
│   ├── hub_courier_planner.py       # Hub courier tracker (bridges to station) [NEW]
│   ├── leadership_dashboard.py      # Executive analytics dashboard [REWRITTEN]
│   └── health_monitor.py            # (also covers station_planner sub-tab)
│
├── assets/
│   ├── _font_b64.txt                # Base64-encoded FedExSansArabic-Medium.ttf
│   └── FedExSansArabic_Md.ttf       # Original font file
│
├── data/                            # Runtime data directory (auto-created)
│   ├── AERO_USERS.xlsx              # User credentials (bcrypt hashed)
│   ├── FAMIS_UPLOADED_FILES.xlsx    # Station FAMIS upload store
│   ├── FAMIS_REPORT_DATA.xlsx       # Station published health reports (4 sheets)
│   ├── HUB_UPLOADED_FILES.xlsx      # Hub FAMIS upload store [NEW]
│   └── HUB_REPORT_DATA.xlsx         # Hub published health reports (4 sheets) [NEW]
│
└── tests/
    ├── __init__.py
    ├── test_area_calculator.py      # 71 tests total (all passing)
    ├── test_health.py
    ├── test_resource_calculator.py
    └── test_security.py
```

---

## 3. User Roles & Navigation

| Role | Pages | Purpose |
|------|-------|---------|
| **Facility** | Home, Station Planner, Hub Planner, Admin Config | Day-to-day facility operations team |
| **Leadership** | Home, Executive Dashboard | Executive analytics overview of Station / Hub health |
| **Operations** | Home, Station, Hub, Analytics | Cross-functional oversight role [NEW] |

Roles are stored in `VALID_ROLES` in `aero/auth/service.py`.

---

## 4. Authentication

- **Store**: `data/AERO_USERS.xlsx` — columns: `username`, `password_hash`, `role`, `display_name`
- **Algorithm**: bcrypt (work factor 12), per-user salt
- **Legacy support**: SHA-256 hashes transparently upgraded to bcrypt on next login
- **Seeding**: `seed_users()` in `service.py` reads initial credentials from env vars (no hardcoded credentials)
- **Session keys**: `aero_authenticated` (bool), `aero_user` (dict with `username`, `role`, `display_name`)

---

## 5. Core Business Logic

### 5.1 Area Calculator (`aero/core/area_calculator.py`)
Calculates spatial requirements from daily volume.

Key formula:
```
pallets_required = ceil(daily_volume / packs_per_pallet)
avg_hourly_pallets = ceil(pallets_required * max_volume_percent / 100)
base_area = avg_hourly_pallets * PALLET_AREA_SQM
area_with_aisle = base_area / (1 - aisle_percent/100)
sorting_area = area_with_aisle * sorting_percent / 100
cage_area = model-based lookup (A/B/C based on volume)
total_operational_area = sorting_area + cage_area + equipment_area
```

### 5.2 Resource Calculator (`aero/core/resource_calculator.py`)
Calculates staffing requirements (OSA, LASA, Dispatcher, Trace Agent roles).

Key inputs: shift hours, absenteeism %, roster buffer %, on-call pickup %, volume  
Output: headcount per role per shift

### 5.3 Courier Calculator (`aero/core/courier_calculator.py`)
Calculates courier requirements from volume and productivity.

Key formula:
```
required_couriers = ceil(daily_packages / (STANDARD_PRODUCTIVITY * shift_hours))
courier_gap = required_couriers - available_couriers
```

### 5.4 Health Scoring (`aero/core/health.py`)
Scores area/resource/courier health as **Healthy / Review / Critical** based on threshold comparisons with FAMIS actuals.

---

## 6. Data Layer

### Station Data (`aero/data/excel_store.py`)
- **FAMIS_UPLOADED_FILES.xlsx** — raw uploaded FAMIS rows, sheet="FAMIS_DATA"
- **FAMIS_REPORT_DATA.xlsx** — published health reports, 4 sheets:
  - `TOTAL SUMMARY`
  - `AREA HEALTH SUMMARY`
  - `RESOURCE HEALTH SUMMARY`
  - `COURIER HEALTH SUMMARY`

### Hub Data (`aero/data/hub_store.py`) [NEW]
- **HUB_UPLOADED_FILES.xlsx** — raw hub FAMIS rows, sheet="HUB_DATA"
- **HUB_REPORT_DATA.xlsx** — published hub health reports, same 4 sheets

Both stores implement:
- `_sanitize_cell()` — formula injection prevention (cell values starting with `=+-@|%` are prefixed with `'`)
- `_atomic_write()` — crash-safe atomic temp-file write using `os.replace()`
- Upsert pattern on `(DATE, LOC ID)` composite key — no duplicate rows

---

## 7. UI System

### CSS Variables (`aero/ui/styles.py`)
| Variable | Value |
|----------|-------|
| `--fc-purple` | `#4D148C` (FedEx primary brand purple) |
| `--fc-orange` | `#FF6200` (FedEx secondary brand orange) |
| `--font-sans` | `FedExSansArabic` → Inter → DM Sans → system stack |
| `--font-head` | `FedExSansArabic` → DM Sans → system stack |

### Font
- **FedEx Sans Arabic Medium** loaded from `assets/_font_b64.txt` (base64-encoded TTF)
- Injected as CSS `@font-face` at runtime by `apply_styles()` in `styles.py`
- Falls back gracefully to Inter/DM Sans if font file unavailable

### Session State
All session state keys are initialized by `init_session_state()` in `aero/ui/session.py`.

Station keys: `famis_data`, `famis_data_raw`, `master_data`, `selected_date`, ...  
Hub keys (same logic, `hub_` prefixed): `hub_famis_data`, `hub_master_data`, `hub_selected_date`, ...

### Hub Session Namespace Pattern
All hub pages use:
```python
_P = "hub_"
def _ss(key, default=None): return st.session_state.get(f"{_P}{key}", default)
def _ss_set(key, val): st.session_state[f"{_P}{key}"] = val
```
This ensures complete isolation between Station and Hub session state.

---

## 8. Excel Data Sheets

### FAMIS Upload Columns (expected in uploaded file)
`loc_id`, `date`, `pk_gross_tot`, `pk_ib`, `pk_ob`, `pk_roc`, `st_cr_or`, `st_h_or`, `pk_st_or`, `pk_fte`, `emp_reported_pct`

### Health Summary Sheet Columns
`DATE`, `LOC ID`, `STATUS`, `VOLUME`, `AREA REQUIRED`, `AREA ACTUAL`, ... (varies by module)

---

## 9. Configuration Files

### `aero/config/tact.json`
TACT (Task Activity Completion Time) standards for resource planning. Contains time-per-task for OSA, LASA, Dispatcher, Trace Agent roles.

### `aero/config/area.json`
Area planning constants:
- `PALLET_AREA` — sqft per pallet
- `AISLE_PERCENT` — default aisle percentage
- Cage model thresholds (Model A / B / C based on volume ranges)

---

## 10. Deployment

### Local Development
```powershell
cd "AERO-main"
.\.venv\Scripts\Activate.ps1
streamlit run main.py
```

### Environment Variables (Required for first-run user seeding)
```
AERO_ADMIN_USER=<username>
AERO_ADMIN_PASS=<password>
AERO_FACILITY_USER=<username>
AERO_FACILITY_PASS=<password>
```
See `aero/auth/service.py` `seed_users()` for full list.

### Python Version
Python 3.13, Streamlit 1.52.1 (see requirements.txt for full dependencies)

---

## 11. Test Suite

71 tests across 4 modules, all passing.

| File | Coverage |
|------|----------|
| `tests/test_area_calculator.py` | Area calculation formulas, edge cases |
| `tests/test_health.py` | Health scoring thresholds (Healthy/Review/Critical) |
| `tests/test_resource_calculator.py` | Resource staffing calculations |
| `tests/test_security.py` | Auth, password hashing, VALID_ROLES validation |

Run tests:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## 12. Security Compliance

| Ref | Control | Implementation |
|-----|---------|---------------|
| SEC-001 | No hardcoded credentials | All seed credentials from env vars |
| SEC-003 | Bcrypt password hashing | Work factor 12, per-user salt |
| SEC-006 | Formula injection prevention | `_sanitize_cell()` in both excel stores |
| SEC-008 | Session isolation | Role-based routing in `main.py`, hub_ key namespace |
| SEC-009 | Input validation | `VALID_ROLES` set enforced on all user writes |
| DL-008 | Crash-safe writes | `_atomic_write()` with `os.replace()` in all stores |

---

## 13. Known Placeholders (Phase 2+)

| Page | Status | Notes |
|------|--------|-------|

---

## 14. Change History (Final Session)

**Session objectives (last day of internship deliverables):**

1. ✅ **Hub Parity** — Created `hub_store.py`, `hub_health_monitor.py`, `hub_area_planner.py`, `hub_resource_planner.py`, `hub_courier_planner.py`; updated `hub_planner.py` to use all 4 tabs
2. ✅ **Leadership Dashboard** — Full rewrite with live KPI cards, Station+Hub status distribution, volume trends, Services Phase 2 placeholders
3. ✅ **Operations Role** — Added to `VALID_ROLES`, routed in `main.py` with Station+Hub+Analytics access
4. ✅ **FedEx Sans Arabic Font** — Base64 font injected via CSS `@font-face` in `styles.py`; `--font-sans` and `--font-head` updated
5. ✅ **Session State** — Hub keys added to `init_session_state()` in `session.py`
6. ✅ **Context** — This file

All 71 tests passing after all changes.
