import os
import streamlit as st

from aero import ASSETS_DIR


def _load_font_face() -> str:
    """Return a CSS @font-face block using the embedded FedEx Sans Arabic font."""
    font_b64_path = os.path.join(ASSETS_DIR, "_font_b64.txt")
    try:
        with open(font_b64_path, "r", encoding="utf-8") as f:
            b64 = f.read().strip()
        return (
            "@font-face {"
            "font-family:'FedExSansArabic';"
            f"src:url('data:font/truetype;base64,{b64}') format('truetype');"
            "font-weight:500;font-style:normal;font-display:swap;"
            "}"
        )
    except Exception:
        return ""


def apply_styles():
    _font_face = _load_font_face()
    # Inject the brand font first so all subsequent CSS can reference it
    if _font_face:
        st.markdown(f"<style>{_font_face}</style>", unsafe_allow_html=True)
    st.markdown("""
    <style>
    @import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=DM+Sans:wght@400;500;600;700;800&display=swap");

    :root {
        --fc-purple:       #4D148C;
        --fc-purple-mid:   #671CAA;
        --fc-purple-dark:  #3C1080;
        --fc-orange:       #FF6200;
        --fc-orange-dark:  #E45528;
        --fc-white:        #FFFFFF;
        --gray-90:  #1A1A1A;
        --gray-80:  #333333;
        --gray-70:  #565656;
        --gray-50:  #8E8E8E;
        --gray-30:  #C8C8C8;
        --gray-20:  #E3E3E3;
        --gray-10:  #F2F2F2;
        --gray-05:  #FAFAFA;
        --dig-blue:   #007AB7;
        --dig-green:  #008A00;
        --dig-red:    #DE002E;
        --dig-yellow: #F7B118;
        --font-sans: "FedExSansArabic", "Inter", "DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        --font-head: "FedExSansArabic", "DM Sans", "Inter", sans-serif;
        --r-xs: 2px; --r-sm: 4px; --r-md: 8px; --r-lg: 12px; --r-xl: 16px; --r-pill: 100px;
        --sh-xs: 0 1px 2px rgba(0,0,0,0.05);
        --sh-sm: 0 1px 4px rgba(0,0,0,0.08);
        --sh-md: 0 4px 14px rgba(0,0,0,0.10);
        --sh-lg: 0 8px 28px rgba(0,0,0,0.12);
        --sh-pu: 0 4px 16px rgba(77,20,140,0.28);
        --sh-or: 0 4px 16px rgba(255,98,0,0.28);
        /* Info / guidance background using brand purple tint (org-compliant) */
        --info-bg: rgba(77,20,140,0.06);
        --info-text: #3C1080;
        /* Status color tokens (card backgrounds, borders, and text) */
        --status-healthy-bg: #ECFDF5;
        --status-healthy-border: #E6F4E6;
        --status-healthy-text: #047857;
        --status-healthy-subtext: #059669;
        --status-healthy-subtext-2: #065f46;

        --status-review-bg: #FFFBEB;
        --status-review-border: #FEE3C3;
        --status-review-text: #D97706;
        --status-review-subtext: #B45309;
        --status-review-subtext-2: #92400e;

        --status-critical-bg: #FEF2F2;
        --status-critical-border: #FECACA;
        --status-critical-text: #DC2626;
        --status-critical-subtext: #991B1B;
        --status-critical-subtext-2: #7f1d1d;

        --status-neutral-bg: #F2F2F2;
        --status-neutral-border: #D1D5DB;
        --status-neutral-text: #333333;
        --status-neutral-subtext: #565656;

        --status-most-affected-bg: #FFF7F7;
        --status-most-affected-border: #FECACA;
    }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        font-family: var(--font-sans) !important;
        color: var(--gray-80) !important;
        background-color: var(--gray-05) !important;
        -webkit-font-smoothing: antialiased !important;
    }
    #MainMenu { visibility: hidden !important; }
    footer[data-testid="stDecoration"] { display: none !important; }

    /* Hide the native Streamlit header bar visually while keeping it in DOM
       (sidebar toggle button is in the sidebar itself, NOT in the header) */
    header[data-testid="stHeader"] {
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        overflow: visible !important;
    }
    /* Keep Deploy/toolbar buttons accessible but out of normal flow */
    [data-testid="stToolbar"] {
        top: 4px !important;
        right: 8px !important;
    }

    .main .block-container,
    [data-testid="stMain"] .block-container {
        padding: 0 2rem 3rem 2rem !important;
        max-width: 100% !important;
    }

    *, *::before, *::after { box-sizing: border-box; }
    h1,h2,h3,h4,h5,h6 { font-family:var(--font-head) !important; color:var(--gray-90) !important; letter-spacing:-0.3px !important; margin-top:0; }
    h1 { font-size:22px !important; font-weight:800 !important; }
    h2 { font-size:17px !important; font-weight:700 !important; }
    h3 { font-size:14px !important; font-weight:700 !important; }
    p  { font-family:var(--font-sans) !important; line-height:1.55 !important; }
    /* Ensure all Streamlit column children fill their width */
    [data-testid="stColumn"] { min-width: 0 !important; }
    [data-testid="stVerticalBlock"] { width: 100% !important; }
    /* Fix input/select widths */
    [data-testid="stTextInput"], [data-testid="stNumberInput"],
    [data-testid="stSelectbox"], [data-testid="stMultiSelect"],
    [data-testid="stDateInput"] { width: 100% !important; }
    [data-testid="stTextInput"] > div, [data-testid="stNumberInput"] > div,
    [data-testid="stSelectbox"] > div { width: 100% !important; }

    /* ── SIDEBAR ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #3C1080 0%, #4D148C 60%, #5A1BA0 100%) !important;
        border-right: none !important;
        box-shadow: 3px 0 20px rgba(0,0,0,0.22) !important;
    }
    section[data-testid="stSidebar"] > div:first-child { background:transparent !important; }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] li { color:rgba(255,255,255,0.9) !important; }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] h2 {
        font-size: 9px !important; font-weight: 800 !important;
        text-transform: uppercase !important; letter-spacing: 2.5px !important;
        color: rgba(255,255,255,0.38) !important; padding: 1rem 1rem 0.3rem !important;
        margin: 0 !important; border-top: 1px solid rgba(255,255,255,0.07) !important;
        font-family: var(--font-sans) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] h2:first-of-type { border-top:none !important; padding-top:.5rem !important; }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
        border-radius: var(--r-sm) !important; margin: 1px 10px !important;
        padding: 8px 12px !important; font-size: 13px !important; font-weight: 500 !important;
        color: rgba(255,255,255,0.80) !important; text-decoration: none !important;
        border-left: 3px solid transparent !important;
        transition: background .18s ease, border-left-color .18s ease, color .18s ease !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
        background: rgba(255,255,255,0.10) !important;
        border-left-color: var(--fc-orange) !important; color: var(--fc-white) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-selected="true"] {
        background: rgba(255,255,255,0.15) !important;
        border-left-color: var(--fc-orange) !important; color: var(--fc-white) !important; font-weight: 700 !important;
        box-shadow: inset 0 0 12px rgba(255,255,255,0.04) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
        background: rgba(255,255,255,0.10) !important; border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: var(--r-sm) !important; display:flex !important; visibility:visible !important; opacity:1 !important; z-index:9999 !important;
        transition: background .18s ease !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:hover { background: rgba(255,255,255,0.18) !important; }
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg { fill:rgba(255,255,255,0.9) !important; }
    section[data-testid="stSidebar"] .stDeployButton { display:none !important; }

    /* ── TABS — Rounded Outlined Button Style (FedEx reference) ── */
    div[data-testid="stTabs"] [data-baseweb="tab-list"],
    .stTabs [data-baseweb="tab-list"] {
        background: transparent !important; border: none !important;
        border-bottom: none !important;
        gap: 10px !important; padding: 6px 0 !important; overflow-x: auto !important;
    }
    div[data-testid="stTabs"] button[role="tab"],
    .stTabs [data-baseweb="tab"] {
        font-family: var(--font-sans) !important; font-size: 12px !important;
        font-weight: 700 !important; letter-spacing: 1px !important; text-transform: uppercase !important;
        color: var(--gray-70) !important; background: var(--fc-white) !important;
        border: 2px solid var(--gray-30) !important;
        border-radius: var(--r-md) !important; padding: 10px 28px !important;
        margin: 0 !important; cursor: pointer !important;
        outline: none !important; white-space: nowrap !important; box-shadow: none !important;
        transform: none !important;
        transition: color .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover,
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--fc-purple) !important; background: rgba(77,20,140,0.03) !important;
        border-color: var(--fc-purple) !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
    .stTabs [aria-selected="true"] {
        color: var(--fc-purple) !important; font-weight: 800 !important;
        background: var(--fc-white) !important;
        border: 2px solid var(--fc-purple) !important;
        box-shadow: 0 3px 0 0 var(--fc-purple) !important;
        transform: none !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-highlight"],
    div[data-testid="stTabs"] [data-baseweb="tab-border"],
    .stTabs [data-baseweb="tab-border"] { display:none !important; height:0 !important; background:transparent !important; }
    div[data-testid="stTabs"] [data-baseweb="tab-panel"],
    .stTabs [data-baseweb="tab-panel"] { padding: 0.5rem 0 0 0 !important; border: none !important; }

    /* ── BUTTONS ── */
    [data-testid="stBaseButton-primary"], button[kind="primary"] {
        background: var(--fc-purple) !important; color: var(--fc-white) !important;
        border: none !important; border-radius: var(--r-sm) !important;
        font-family: var(--font-sans) !important; font-size: 12px !important;
        font-weight: 800 !important; letter-spacing: 1px !important; text-transform: uppercase !important;
        padding: 10px 22px !important; box-shadow: var(--sh-xs) !important;
        transition: background .18s ease, box-shadow .18s ease !important;
    }
    [data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {
        background: var(--fc-purple-mid) !important; box-shadow: var(--sh-pu) !important;
    }
    [data-testid="stBaseButton-secondary"], .stButton > button, button[kind="secondary"] {
        background: var(--fc-purple) !important; color: var(--fc-white) !important;
        border: none !important; border-radius: var(--r-sm) !important;
        font-family: var(--font-sans) !important; font-size: 12px !important;
        font-weight: 800 !important; letter-spacing: 1px !important; text-transform: uppercase !important;
        padding: 10px 22px !important; box-shadow: var(--sh-xs) !important;
        transition: background .18s ease, box-shadow .18s ease !important;
    }
    [data-testid="stBaseButton-secondary"]:hover, .stButton > button:hover, button[kind="secondary"]:hover {
        background: var(--fc-purple-mid) !important; box-shadow: var(--sh-pu) !important;
    }
    [data-testid="stBaseButton-tertiary"], button[kind="tertiary"] {
        background: transparent !important; color: var(--fc-purple) !important;
        border: 2px solid var(--fc-purple) !important; border-radius: var(--r-sm) !important;
        font-family: var(--font-sans) !important; font-size: 12px !important;
        font-weight: 700 !important; letter-spacing: 1px !important; text-transform: uppercase !important;
        transition: all .18s ease !important;
    }
    [data-testid="stBaseButton-tertiary"]:hover, button[kind="tertiary"]:hover {
        background: rgba(77,20,140,0.07) !important;
    }

    /* ── FORM INPUTS ── */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-sm) !important;
        font-family: var(--font-sans) !important; font-size: 13px !important;
        color: var(--gray-80) !important; background: var(--fc-white) !important;
        padding: 8px 10px !important; transition: border-color .18s ease, box-shadow .18s ease !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {
        border-color: var(--fc-purple) !important; box-shadow: 0 0 0 3px rgba(77,20,140,0.10) !important; outline: none !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-sm) !important;
        background: var(--fc-white) !important; font-size: 13px !important; color: var(--gray-80) !important;
    }
    [data-testid="stSelectbox"]:focus-within [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"]:focus-within [data-baseweb="select"] > div {
        border-color: var(--fc-purple) !important; box-shadow: 0 0 0 3px rgba(77,20,140,0.10) !important;
    }
    [data-baseweb="popover"] [data-baseweb="menu"] {
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-md) !important;
        box-shadow: var(--sh-md) !important; overflow: hidden !important;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="popover"] [data-highlighted="true"] {
        background: rgba(77,20,140,0.07) !important; color: var(--fc-purple) !important;
    }
    [data-baseweb="popover"] [aria-selected="true"] {
        background: rgba(77,20,140,0.13) !important; color: var(--fc-purple) !important; font-weight: 700 !important;
    }
    [data-testid="stDateInput"] input {
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-sm) !important; font-size: 13px !important;
    }
    label[data-testid="stWidgetLabel"],
    [data-testid="stTextInput"] label,   [data-testid="stNumberInput"] label,
    [data-testid="stSelectbox"] label,   [data-testid="stMultiSelect"] label,
    [data-testid="stDateInput"] label,   [data-testid="stSlider"] label {
        color: var(--gray-70) !important; font-size: 10px !important; font-weight: 700 !important;
        text-transform: uppercase !important; letter-spacing: 0.9px !important; font-family: var(--font-sans) !important;
    }
    [data-testid="stSlider"] [role="slider"] { background: var(--fc-purple) !important; border-color: var(--fc-purple) !important; }

    /* ── RADIO PILL TOGGLE ── */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display:flex !important; gap:0 !important; background:var(--gray-10) !important;
        border-radius:var(--r-pill) !important; padding:3px !important;
        border:1px solid var(--gray-20) !important; width:fit-content !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        background:transparent !important; border:none !important; border-radius:var(--r-pill) !important;
        padding:7px 20px !important; font-weight:600 !important; font-size:11px !important;
        letter-spacing:0.6px !important; text-transform:uppercase !important;
        cursor:pointer !important; transition:all .22s ease !important;
        color:var(--gray-70) !important; margin:0 !important;
        display:flex !important; align-items:center !important; white-space:nowrap !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover { color:var(--fc-purple) !important; background:rgba(77,20,140,0.07) !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked),
    div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] {
        background:var(--fc-purple) !important; color:var(--fc-white) !important; box-shadow:var(--sh-pu) !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] p,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) span,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] span { color:var(--fc-white) !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child,
    div[data-testid="stRadio"] svg { display:none !important; }

    /* ── METRICS ── */
    [data-testid="stMetric"], [data-testid="metric-container"] {
        background: var(--fc-white) !important; border: 1px solid var(--gray-20) !important;
        border-top: 3px solid var(--fc-purple) !important; border-radius: var(--r-md) !important;
        padding: 14px 16px 10px !important; box-shadow: var(--sh-xs) !important;
        transition: transform .15s ease, box-shadow .15s ease, border-top-color .15s ease !important;
    }
    [data-testid="stMetric"]:hover, [data-testid="metric-container"]:hover {
        transform: translateY(-2px) !important; box-shadow: var(--sh-md) !important; border-top-color: var(--fc-purple-mid) !important;
    }
    [data-testid="stMetricLabel"] p { color:var(--gray-50) !important; font-size:10px !important; font-weight:700 !important; text-transform:uppercase !important; letter-spacing:1px !important; }
    [data-testid="stMetricValue"]   { color:var(--gray-90) !important; font-size:26px !important; font-weight:800 !important; font-family:var(--font-head) !important; line-height:1.1 !important; }

    /* ── EXPANDERS ── */
    [data-testid="stExpander"] {
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-md) !important;
        background: var(--fc-white) !important; box-shadow: var(--sh-xs) !important;
        overflow: hidden !important; margin-bottom: 8px !important;
    }
    [data-testid="stExpander"] summary, .streamlit-expanderHeader {
        background: var(--gray-05) !important; border-bottom: 1px solid var(--gray-20) !important;
        font-family: var(--font-head) !important; font-weight: 700 !important; font-size: 13px !important;
        color: var(--gray-80) !important; padding: 10px 14px !important; border-radius: 0 !important;
        transition: background .15s ease, color .15s ease !important;
    }
    [data-testid="stExpander"] summary:hover, .streamlit-expanderHeader:hover { background:rgba(77,20,140,0.04) !important; color:var(--fc-purple) !important; }
    [data-testid="stExpander"] > div:last-child { padding: 12px 14px !important; }

    /* ── FILE UPLOADER ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed var(--gray-30) !important; border-radius: var(--r-md) !important;
        background: var(--gray-05) !important; padding: 24px 16px !important;
        transition: border-color .2s ease, background .2s ease !important;
    }
    [data-testid="stFileUploader"]:hover { border-color: var(--fc-purple) !important; background: rgba(77,20,140,0.02) !important; }
    [data-testid="stFileUploader"] section { border:none !important; background:transparent !important; }
    [data-testid="stFileUploader"] button {
        background: var(--fc-white) !important; color: var(--gray-80) !important;
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-sm) !important;
        font-size: 12px !important; font-weight: 600 !important; padding: 5px 14px !important; text-transform: none !important;
    }
    [data-testid="stFileUploader"] button:hover { border-color:var(--fc-purple) !important; color:var(--fc-purple) !important; background:rgba(77,20,140,0.04) !important; box-shadow:none !important; }

    /* ── DATA TABLES ── */
    [data-testid="stDataFrame"], .stDataFrame {
        border: 1px solid var(--gray-20) !important; border-radius: var(--r-md) !important;
        overflow: hidden !important; box-shadow: var(--sh-sm) !important;
    }
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] [role="columnheader"] {
        background: var(--fc-purple) !important; color: var(--fc-white) !important;
        font-family: var(--font-sans) !important; font-weight: 700 !important; font-size: 10px !important;
        text-transform: uppercase !important; letter-spacing: 0.8px !important;
        border-bottom: 3px solid var(--fc-orange) !important;
    }
    /* Glide Data Grid header override */
    [data-testid="stDataFrame"] [data-testid="glide-cell"][aria-colindex] {
        font-family: var(--font-sans) !important; font-size: 12px !important;
    }
    [data-testid="stDataFrame"] table {
        border-bottom: 3px solid var(--fc-orange) !important;
    }
    /* st.table header */
    .stTable thead th {
        background: var(--fc-purple) !important; color: var(--fc-white) !important;
        font-family: var(--font-sans) !important; font-weight: 700 !important; font-size: 10px !important;
        text-transform: uppercase !important; letter-spacing: 0.8px !important;
        border-bottom: 3px solid var(--fc-orange) !important;
        padding: 10px 12px !important;
    }
    .stTable tbody td {
        font-family: var(--font-sans) !important; font-size: 12px !important;
        padding: 8px 12px !important; border-bottom: 1px solid var(--gray-10) !important;
    }
    .stTable tbody tr:last-child td {
        border-bottom: 3px solid var(--fc-orange) !important;
    }

    /* ── ALERTS ── */
    /* Use brand purple tint for informational banners to align with org policy and provided reference artwork */
    [data-testid="stInfo"]    { background: var(--info-bg) !important; border-left:4px solid var(--fc-purple) !important; border-radius:0 var(--r-md) var(--r-md) 0 !important; border-top:none !important; border-right:none !important; border-bottom:none !important; color: var(--info-text) !important; }
    [data-testid="stSuccess"] { background:#E8F5E8 !important; border-left:4px solid var(--dig-green)  !important; border-radius:0 var(--r-md) var(--r-md) 0 !important; border-top:none !important; border-right:none !important; border-bottom:none !important; color:#0A3A0A !important; }
    [data-testid="stWarning"] { background:#FEF3C7 !important; border-left:4px solid var(--dig-yellow) !important; border-radius:0 var(--r-md) var(--r-md) 0 !important; border-top:none !important; border-right:none !important; border-bottom:none !important; color:#7C4F00 !important; }
    [data-testid="stError"]   { background:#FDE8EC !important; border-left:4px solid var(--dig-red)    !important; border-radius:0 var(--r-md) var(--r-md) 0 !important; border-top:none !important; border-right:none !important; border-bottom:none !important; color:#5A0014 !important; }

    /* ── PROGRESS ── */
    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, var(--fc-purple-dark) 0%, var(--fc-purple) 60%, var(--fc-purple-mid) 100%) !important;
        border-radius: var(--r-pill) !important;
    }

    /* ── DIVIDERS ── */
    hr { border:none !important; height:1px !important; background:var(--gray-20) !important; margin:1.25rem 0 !important; opacity:1 !important; }

    /* ── SCROLLBAR ── */
    ::-webkit-scrollbar { width:5px; height:5px; }
    ::-webkit-scrollbar-track { background:var(--gray-05); }
    ::-webkit-scrollbar-thumb { background:var(--gray-30); border-radius:3px; }
    ::-webkit-scrollbar-thumb:hover { background:var(--gray-50); }

    /* ── TOPBAR (rendered by render_header) ── */
    .fedex-topbar {
        display:flex !important; align-items:center !important; justify-content:space-between !important;
        padding:12px 8px !important; border-bottom:3px solid var(--fc-purple) !important;
        margin-bottom:1rem !important; background:var(--fc-white) !important;
    }
    .fedex-topbar-left  { display:flex !important; align-items:center !important; gap:14px !important; }
    .fedex-logo-text {
        font-family:"Arial Black",Arial,sans-serif !important; font-size:40px !important;
        font-weight:900 !important; letter-spacing:-1px !important; line-height:1 !important;
        flex-shrink:0 !important; user-select:none !important;
    }
    .fedex-topbar-sep { color:var(--gray-30) !important; font-size:24px !important; font-weight:100 !important; flex-shrink:0 !important; line-height:1 !important; margin:0 6px !important; }
    .fedex-topbar-title-block { display:flex !important; flex-direction:column !important; gap:4px !important; }
    .fedex-topbar-title { font-family:var(--font-head) !important; font-size:20px !important; font-weight:800 !important; color:var(--gray-90) !important; line-height:1.15 !important; }
    .fedex-topbar-subtitle { font-family:var(--font-sans) !important; font-size:11px !important; color:var(--gray-50) !important; font-weight:700 !important; letter-spacing:0.7px !important; text-transform:uppercase !important; }
    .fedex-topbar-right { display:flex !important; align-items:center !important; gap:8px !important; }
    .fedex-module-badge {
        background:var(--fc-purple) !important; color:var(--fc-white) !important;
        font-family:var(--font-sans) !important; font-size:10px !important; font-weight:800 !important;
        letter-spacing:1px !important; padding:6px 14px !important;
        border-radius:var(--r-sm) !important; text-transform:uppercase !important; white-space:nowrap !important;
    }
    .fedex-user-badge {
        display:flex !important; align-items:center !important; gap:8px !important;
        background:var(--gray-05) !important; border:1px solid var(--gray-20) !important;
        border-radius:var(--r-pill) !important; padding:4px 14px 4px 4px !important;
        white-space:nowrap !important;
    }
    .fedex-user-avatar {
        width:30px !important; height:30px !important; border-radius:50% !important;
        background:var(--fc-purple) !important; color:var(--fc-white) !important;
        font-family:var(--font-sans) !important; font-size:13px !important; font-weight:800 !important;
        display:flex !important; align-items:center !important; justify-content:center !important;
        letter-spacing:0.5px !important; flex-shrink:0 !important;
    }
    .fedex-user-info { display:flex !important; flex-direction:column !important; gap:1px !important; }
    .fedex-user-name {
        font-family:var(--font-sans) !important; font-size:13px !important; font-weight:700 !important;
        color:var(--gray-80) !important; line-height:1.2 !important;
    }
    .fedex-user-role {
        font-family:var(--font-sans) !important; font-size:11px !important; font-weight:600 !important;
        color:var(--gray-50) !important; text-transform:uppercase !important; letter-spacing:0.5px !important;
        line-height:1.2 !important;
    }
    /* Large variant for topbar */
    .fedex-user-badge-lg {
        gap:12px !important;
        padding:7px 22px 7px 7px !important;
    }
    .fedex-user-avatar-lg {
        width:40px !important; height:40px !important; font-size:18px !important;
    }
    .fedex-user-info-lg {
        gap:2px !important;
    }
    .fedex-user-name-lg {
        font-size:16px !important;
    }
    .fedex-user-role-lg {
        font-size:12px !important;
    }

    /* ── FOOTER (rendered by render_footer) ── */
    .fedex-footer { margin-top:2rem !important; padding-top:1rem !important; border-top:1px solid var(--gray-20) !important; text-align:center !important; }
    .fedex-footer-logo { font-family:"Arial Black",Arial,sans-serif !important; font-size:28px !important; font-weight:900 !important; letter-spacing:-1px !important; display:inline-block !important; margin-bottom:6px !important; }
    .fedex-footer-copy { font-size:10px !important; color:var(--gray-50) !important; font-family:var(--font-sans) !important; letter-spacing:0.3px !important; }

    /* ── UTILITY CLASSES ── */
    .section-banner {
        background: var(--fc-purple) !important; color:var(--fc-white) !important;
        font-family:var(--font-head) !important; font-weight:700 !important; font-size:14px !important;
        padding:13px 20px !important; border-radius:var(--r-md) !important; margin:.75rem 0 !important;
    }
    .table-header-box {
        font-family:var(--font-head) !important; font-weight:700 !important; font-size:15px !important;
        color:var(--gray-90) !important; padding:10px 0 8px 0 !important;
        border-bottom:3px solid var(--fc-purple) !important; margin:1rem 0 .75rem 0 !important; background:transparent !important;
    }
    .fedex-card {
        background:var(--fc-white) !important; border:1px solid var(--gray-20) !important;
        border-radius:var(--r-lg) !important; padding:16px !important; box-shadow:var(--sh-xs) !important;
        transition:transform .15s ease, box-shadow .15s ease !important;
    }
    .fedex-card:hover { transform:translateY(-2px) !important; box-shadow:var(--sh-md) !important; }
    .hm-card {
        background:var(--fc-white) !important; border:1px solid var(--gray-20) !important;
        border-top:3px solid var(--fc-purple) !important; border-radius:var(--r-md) !important;
        padding:12px 14px !important; box-shadow:var(--sh-xs) !important;
        transition:transform .15s ease, border-top-color .15s ease !important;
    }
    .hm-card:hover { transform:translateY(-1px) !important; }
    .hm-card .hm-title { font-size:10px !important; font-weight:700 !important; color:var(--gray-50) !important; text-transform:uppercase !important; letter-spacing:.9px !important; }
    .hm-card .hm-value { font-size:18px !important; font-weight:800 !important; color:var(--gray-80) !important; font-family:var(--font-head) !important; }
    .info-panel { background:rgba(77,20,140,0.04) !important; border-left:4px solid var(--fc-purple) !important; border-radius:0 var(--r-md) var(--r-md) 0 !important; padding:10px 14px !important; margin:.5rem 0 !important; font-size:13px !important; color:var(--gray-70) !important; }
    .stat-card { background:var(--fc-white) !important; border:1px solid var(--gray-20) !important; border-radius:var(--r-md) !important; padding:16px 14px !important; text-align:center !important; box-shadow:var(--sh-xs) !important; }
    .stat-card-label { font-size:10px !important; font-weight:700 !important; color:var(--gray-50) !important; text-transform:uppercase !important; letter-spacing:.9px !important; margin-bottom:6px !important; }
    .stat-card-value { font-size:30px !important; font-weight:800 !important; color:var(--gray-90) !important; font-family:var(--font-head) !important; line-height:1 !important; }
    .badge { display:inline-flex !important; align-items:center !important; padding:2px 10px !important; border-radius:var(--r-pill) !important; font-size:11px !important; font-weight:700 !important; letter-spacing:.4px !important; }
    .badge-green  { background:#E8F5E8; color:#006600; }
    .badge-red    { background:#FDE8EC; color:#B50020; }
    .badge-yellow { background:#FEF3C7; color:#7C4F00; }
    .badge-purple { background:rgba(77,20,140,0.10); color:#4D148C; }
    .badge-gray   { background:var(--gray-10); color:var(--gray-50); }
    .page-divider { height:1px; background:var(--gray-20); margin:1.5rem 0; border:none; }

    </style>
    """, unsafe_allow_html=True)
