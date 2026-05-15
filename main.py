import os
import sys
import streamlit as st

# Ensure project root is on sys.path so app.* imports resolve inside st.navigation exec()
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from aero.ui.sidebar import render_sidebar
from aero.ui.styles import apply_styles
from aero.ui.session import init_session_state
from aero.auth.service import (
    is_authenticated,
    get_current_user,
    logout_user,
    seed_users,
)

# ============================================================
# PAGE CONFIG — 
# ============================================================
st.set_page_config(
    page_title="AERO - Automated Evaluation Of Resource Occupancy",
    layout="wide",
    page_icon="🏠",
    initial_sidebar_state="expanded",
)

# Seed default users on first run
seed_users()

# Initialize all session state keys with defaults (CQ-009)
init_session_state()
# ============================================================
# ⚠️ DEMO MODE: FAKE SESSION INJECTOR (TEMPORARY)
# ------------------------------------------------------------
# This block bypasses login by injecting a mock user session.
# - Safe to delete entirely after demo
# - Does NOT modify core auth logic
# - Keeps role-based navigation intact
#
# TO REMOVE LATER:
# უბრალოდ delete this entire block — no other changes needed.
# ============================================================

DEMO_MODE = False  # 🔁 Set to True for demo bypass (uses fake session)

if DEMO_MODE:
    # NOTE: For demo mode to work properly, use the correct session keys
    st.session_state["aero_authenticated"] = True
    st.session_state["aero_user"] = {
        "user_id": "demo_user",
        "display_name": "Demo User",
        "role": "Services",  # 🔁 Change role if you want different view
    }

# ============================================================

# Apply global styles (CSS variables, fonts, brand colours)
apply_styles()

# ============================================================
# AUTH GATE — show login page if not authenticated
# ============================================================
if not is_authenticated():
    # Show only the login page (sidebar hidden by login.py CSS)
    pg = st.navigation(
        [st.Page("pages/login.py", title="Sign In", icon="🔐")],
        position="hidden",
    )
    pg.run()
    st.stop()

# ============================================================
# AUTHENTICATED — build role-based navigation
# ============================================================
user = get_current_user()
role = user["role"]

# Render sidebar (no user info if header shows it)
render_sidebar(user=user)

# Only show sign out button in sidebar (no user info)
with st.sidebar:
    # Enhanced sign out button with working logout logic
    signout_btn = st.button("🔚 SIGN OUT", key="logout_btn", use_container_width=True)
    if signout_btn:
        logout_user()
        st.rerun()
    st.markdown("""
    <style>
    section[data-testid='stSidebar'] button[kind='secondary'] {
        background: linear-gradient(90deg, #FF6200 0%, #E45528 100%) !important;
        color: #fff !important;
        border: none !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        margin: 18px 0 0 0 !important;
        padding: 12px 0 !important;
        width: 100% !important;
        box-shadow: 0 2px 8px rgba(255,98,0,0.10) !important;
        letter-spacing: 0.5px !important;
        transition: background 0.18s, box-shadow 0.18s;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 10px !important;
    }
    section[data-testid='stSidebar'] button[kind='secondary']:hover {
        background: linear-gradient(90deg, #E45528 0%, #FF6200 100%) !important;
        box-shadow: 0 4px 16px rgba(255,98,0,0.18) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# NAVIGATION — strict role-based page structure
# Each role sees ONLY their section — no cross-role leakage.
# ============================================================

if role == "Facility":
    # ── Field Engineer ────────────────────────────────────────
    pages = {
        "UPLOADS & DATA": [
            st.Page("frontend/field/upload_centre.py",
                    title="Data Upload Centre", icon="📤",
                    url_path="upload-centre", default=True),
        ],
        "PLANNING TOOLS": [
            st.Page("frontend/field/planning_suite.py",
                    title="Station Planning", icon="🏢",
                    url_path="station-planning"),
            st.Page("frontend/field/hub_coming_soon.py",
                    title="Hub Planning", icon="🏭",
                    url_path="hub-planning"),
        ],
        "ANALYTICS & CONFIG": [
            st.Page("frontend/field/analytics.py",
                    title="Station Analytics", icon="📊",
                    url_path="station-analytics"),
        ],
    }

elif role == "Gateway":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠",
                    url_path="home", default=True),
        ],
        "GATEWAY": [
            st.Page("frontend/gateway/operations.py",
                    title="Gateway Operations", icon="✈️",
                    url_path="gateway-operations"),
        ],
    }

elif role == "Services":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠",
                    url_path="home", default=True),
        ],
        "SERVICES": [
            st.Page("frontend/services/operations.py",
                    title="Services Operations", icon="🛠️",
                    url_path="services-operations"),
        ],
    }

elif role == "Leadership":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠",
                    url_path="home", default=True),
        ],
        "LEADERSHIP": [
            st.Page("frontend/leadership/dashboard.py",
                    title="Executive Dashboard", icon="👔",
                    url_path="executive-dashboard"),
        ],
    }

elif role == "Operations":
    # ── Admin / Operations — full visibility across ALL modules ──────────────
    pages = {
        "OVERVIEW": [
            st.Page("frontend/admin/overview.py",
                    title="Operations Overview", icon="🏠",
                    url_path="ops-overview", default=True),
        ],
        "FIELD OPERATIONS": [
            st.Page("frontend/field/upload_centre.py",
                    title="Data Upload Centre", icon="📤",
                    url_path="upload-centre"),
            st.Page("frontend/field/planning_suite.py",
                    title="Station Planning", icon=