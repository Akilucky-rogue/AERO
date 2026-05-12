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
# NAVIGATION — role-specific page structure
# ============================================================
if role == "Facility":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        ],
        "FACILITIES": [
            st.Page("pages/station_planner.py", title="Station", icon="🏢"),
            st.Page("pages/hub_planner.py", title="Hub", icon="🏭"),
        ],
        "ADMINISTRATION": [
            st.Page("pages/admin_controls.py", title="Configuration", icon="⚙️"),
        ],
    }
elif role == "Gateway":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        ],
        "GATEWAY": [
            st.Page("pages/gateway_ops.py", title="Gateway Operations", icon="🔗"),
        ],
    }
elif role == "Services":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        ],
        "SERVICES": [
            st.Page("pages/services_ops.py", title="Services Operations", icon="🛠️"),
        ],
    }
elif role == "Leadership":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        ],
        "LEADERSHIP": [
            st.Page("pages/leadership_dashboard.py", title="Executive Dashboard", icon="👔"),
            st.Page("pages/nsl_analytics.py", title="NSL Analytics", icon="📦"),
        ],
    }
elif role == "Operations":
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        ],
        "FACILITIES": [
            st.Page("pages/station_planner.py", title="Station", icon="🏢"),
            st.Page("pages/hub_planner.py", title="Hub", icon="🏭"),
        ],
        "OPERATIONS": [
            st.Page("pages/gateway_ops.py", title="Gateway Operations", icon="✈️"),
            st.Page("pages/services_ops.py", title="Services Operations", icon="🛎️"),
        ],
        "ANALYTICS": [
            st.Page("pages/leadership_dashboard.py", title="Analytics Overview", icon="📊"),
            st.Page("pages/nsl_analytics.py", title="NSL Analytics", icon="📦"),
        ],
    }
else:
    pages = {
        "HOME": [
            st.Page("pages/home.py", title="Home", icon="🏠", default=True),
        ],
    }

pg = st.navigation(pages)
pg.run()
