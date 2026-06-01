"""
aero/ui/session.py — Centralized Streamlit session-state initialization (CQ-009).

Call init_session_state() once from main.py before st.navigation() to ensure
all expected keys exist with sensible defaults.  This prevents per-page
initialization races and makes debugging state-related issues straightforward.
"""

import streamlit as st


def init_session_state() -> None:
    """Initialize all application-level session-state keys with defaults.

    Idempotent: keys that already exist (e.g., after a rerun) are left
    unchanged so that active auth tokens and user data are preserved.
    """
    # ── Authentication (managed by aero.auth.service) ──────────────────────
    if "aero_authenticated" not in st.session_state:
        st.session_state["aero_authenticated"] = False
    if "aero_user" not in st.session_state:
        st.session_state["aero_user"] = None

    # ── Data / upload state (shared across health-monitor pages) ───────────
    if "last_upload_id" not in st.session_state:
        st.session_state["last_upload_id"] = None

    # Primary FAMIS dataset (set by upload_centre, consumed by all planners)
    if "famis_data" not in st.session_state:
        st.session_state["famis_data"] = None
    if "famis_data_raw" not in st.session_state:
        st.session_state["famis_data_raw"] = None
    if "famis_df" not in st.session_state:       # alias kept for legacy compat
        st.session_state["famis_df"] = None
    if "famis_file_name" not in st.session_state:
        st.session_state["famis_file_name"] = None
    if "famis_file_id" not in st.session_state:
        st.session_state["famis_file_id"] = None

    # Facility Master (auto-loaded from FAMIS_META.xlsx on app start)
    if "master_data" not in st.session_state:
        st.session_state["master_data"] = None

    # Upload registry snapshot (list of metadata dicts, drives visibility table)
    if "famis_upload_registry" not in st.session_state:
        st.session_state["famis_upload_registry"] = None

    # ── Planning state (shared across planner pages) ────────────────────────
    if "selected_station" not in st.session_state:
        st.session_state["selected_station"] = None

    # ── UI state ────────────────────────────────────────────────────────────
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = None

    # ── Hub section state (mirrored namespace for Hub Planner) ──────────────
    if "hub_famis_data" not in st.session_state:
        st.session_state["hub_famis_data"] = None
    if "hub_famis_data_raw" not in st.session_state:
        st.session_state["hub_famis_data_raw"] = None
    if "hub_master_data" not in st.session_state:
        st.session_state["hub_master_data"] = None
    if "hub_famis_station" not in st.session_state:
        st.session_state["hub_famis_station"] = ""
    if "hub_selected_date" not in st.session_state:
        st.session_state["hub_selected_date"] = None
    if "hub_famis_file_type" not in st.session_state:
        st.session_state["hub_famis_file_type"] = "Daily"
    if "hub_famis_file_type_saved" not in st.session_state:
        st.session_state["hub_famis_file_type_saved"] = "Daily"
    if "hub_health_active_tab" not in st.session_state:
        st.session_state["hub_health_active_tab"] = "AREA"

