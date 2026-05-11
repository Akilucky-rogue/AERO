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
    if "famis_df" not in st.session_state:
        st.session_state["famis_df"] = None

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

    # ── Services — Delay Prediction Engine ─────────────────────────────────
    # svc_model      : built statistical model dict (None until trained)
    # svc_model_meta : training metadata (filename, row count, date range, trained_at)
    # svc_nsl_df     : parsed NSL DataFrame for current upload session
    # svc_nsl_meta   : parse metadata for the NSL file
    # svc_awb_df     : parsed daily AWB DataFrame
    # svc_awb_meta   : parse metadata for the AWB file
    # svc_pred_df    : prediction results DataFrame (last run)
    if "svc_model" not in st.session_state:
        st.session_state["svc_model"] = None
    if "svc_model_meta" not in st.session_state:
        st.session_state["svc_model_meta"] = None
    if "svc_nsl_df" not in st.session_state:
        st.session_state["svc_nsl_df"] = None
    if "svc_nsl_meta" not in st.session_state:
        st.session_state["svc_nsl_meta"] = None
    if "svc_awb_df" not in st.session_state:
        st.session_state["svc_awb_df"] = None
    if "svc_awb_meta" not in st.session_state:
        st.session_state["svc_awb_meta"] = None
    if "svc_pred_df" not in st.session_state:
        st.session_state["svc_pred_df"] = None

    # ── Services — Delay Prediction Engine ─────────────────────────────────
    # svc_model      : built statistical model dict (None until trained)
    # svc_model_meta : training metadata (filename, row count, date range, trained_at)
    # svc_nsl_df     : parsed NSL DataFrame for current upload session
    # svc_nsl_meta   : parse metadata for the NSL file
    # svc_awb_df     : parsed daily AWB DataFrame
    # svc_awb_meta   : parse metadata for the AWB file
    # svc_pred_df    : prediction results DataFrame (last run)
    if "svc_model" not in st.session_state:
        st.session_state["svc_model"] = None
    if "svc_model_meta" not in st.session_state:
        st.session_state["svc_model_meta"] = None
    if "svc_nsl_df" not in st.session_state:
        st.session_state["svc_nsl_df"] = None
    if "svc_nsl_meta" not in st.session_state:
        st.session_state["svc_nsl_meta"] = None
    if "svc_awb_df" not in st.session_state:
        st.session_state["svc_awb_df"] = None
    if "svc_awb_meta" not in st.session_state:
        st.session_state["svc_awb_meta"] = None
    if "svc_pred_df" not in st.session_state:
        st.session_state["svc_pred_df"] = None

