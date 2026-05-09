# ============================================================
# AERO — Login Page (Split-Screen Professional Layout)
# ============================================================
import streamlit as st
import base64
import os
from aero.auth.service import authenticate, login_user
from aero import ASSETS_DIR

# ── Load logo ────────────────────────────────────────────────
_LOGO_PATH = os.path.join(ASSETS_DIR, "image.png")
try:
    with open(_LOGO_PATH, "rb") as _f:
        _LOGO_B64 = base64.b64encode(_f.read()).decode()
except Exception:
    _LOGO_B64 = ""

if _LOGO_B64:
    _logo_tag = f'<img src="data:image/png;base64,{_LOGO_B64}" alt="FedEx" style="height:72px;object-fit:contain;">'
else:
    _logo_tag = '<span style="font-size:42px;font-weight:800;letter-spacing:-0.5px;"><span style="color:#4D148C;">Fed</span><span style="color:#FF6200;">Ex</span></span>'

# ── Right-panel HTML (pure decorative) ───────────────────────
_right_panel_html = """
<div class="rp">
    <div class="rp-circle rp-c1"></div>
    <div class="rp-circle rp-c2"></div>
    <div class="rp-icons">
        <div class="rp-ico">📊</div>
        <div class="rp-ico">📐</div>
        <div class="rp-ico">🚚</div>
        <div class="rp-ico">👥</div>
    </div>
    <div class="rp-mock">
        <div class="rp-bar b1"></div>
        <div class="rp-bar b2"></div>
        <div class="rp-bar b3"></div>
        <div class="rp-bar b4"></div>
    </div>
    <div class="rp-h">Plan every station,<br>on one platform.</div>
    <div class="rp-s">Area planning, resource allocation, courier tracking &amp; health monitoring — all in one place.</div>
    <div class="rp-dots"><span class="d1"></span><span></span><span></span></div>
</div>
"""

# ── CSS ──────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=DM+Sans:wght@400;500;600;700;800&display=swap");

/* ── HIDE CHROME ── */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
header[data-testid="stHeader"] {{ display:none!important; }}

/* ── PAGE BG — full viewport ── */
[data-testid="stAppViewContainer"] {{ background:#ECEEF1!important; }}
[data-testid="stMain"] {{ background:transparent!important; padding:0!important; }}

/* ── CONTAINER — full width, no padding, vertically centered ── */
.block-container {{
    max-width:100%!important;
    width:100%!important;
    padding:0!important;
    margin:0!important;
}}

/* ── CARD FRAME — full viewport height ── */
.block-container [data-testid="stHorizontalBlock"] {{
    gap:0!important;
    border-radius:0!important;
    overflow:hidden;
    box-shadow:none!important;
    min-height:100vh!important;
    height:100vh!important;
}}

/* ── LEFT COL → white, vertically centered ── */
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child,
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child *[data-testid="stVerticalBlockBorderWrapper"],
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child *[data-testid="stVerticalBlock"] {{
    background:#FFFFFF!important;
}}
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
}}
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child > div:first-child > div:first-child > [data-testid="stVerticalBlock"] {{
    padding:48px 56px 36px!important;
    gap:4px!important;
    max-width:440px!important;
    width:100%!important;
    margin:0 auto!important;
}}

/* ── RIGHT COL → purple gradient, vertically centered ── */
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
    background:linear-gradient(150deg,#4D148C 0%,#5B1FA3 35%,#3D1080 75%,#2D0A5E 100%)!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
}}
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child *[data-testid="stVerticalBlockBorderWrapper"],
.block-container [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child *[data-testid="stVerticalBlock"] {{
    background:transparent!important;
}}

/* ── LEFT PANEL TYPOGRAPHY ── */
.lp-logo {{ margin-bottom:32px; text-align:center; }}
.lp-h {{
    font-family:'DM Sans','Inter',sans-serif;
    font-weight:800; font-size:28px;
    color:#1A1A2E; margin:0 0 6px;
    letter-spacing:-0.5px;
    text-align:center;
}}
.lp-sub {{
    font-family:'Inter',sans-serif;
    font-size:14px; color:#8C8C9A;
    margin:0 0 24px; font-weight:400;
    text-align:center;
}}
.lp-div {{
    height:1px; background:#EBEBEB;
    margin:0 0 20px; position:relative;
}}
.lp-div::after {{
    content:"sign in with credentials";
    position:absolute; top:50%; left:50%;
    transform:translate(-50%,-50%);
    background:#FFFFFF; padding:0 14px;
    font-size:11px; color:#B0B0B0;
    font-family:'Inter',sans-serif;
    font-weight:500; white-space:nowrap;
    letter-spacing:0.4px;
}}
.lp-foot {{
    text-align:center; font-family:'Inter',sans-serif;
    font-size:10px; color:#C0C0C0;
    margin-top:20px; letter-spacing:0.4px;
    text-transform:uppercase; font-weight:600;
}}

/* ── FORM STYLING ── */
[data-testid="stForm"] {{
    border:none!important;
    padding:0!important;
    background:transparent!important;
    margin:0!important;
}}
[data-testid="stForm"] label[data-testid="stWidgetLabel"],
[data-testid="stForm"] .stTextInput label {{
    font-family:'Inter',sans-serif!important;
    font-size:12px!important;
    font-weight:600!important;
    color:#444!important;
    margin-bottom:2px!important;
    text-transform:uppercase!important;
    letter-spacing:0.3px!important;
}}
[data-testid="stForm"] .stTextInput > div {{
    margin-bottom:6px!important;
}}
[data-testid="stForm"] .stTextInput {{
    margin-bottom:6px!important;
}}
[data-testid="stForm"] input {{
    border-radius:10px!important;
    border:1.5px solid #E5E5EA!important;
    padding:12px 16px!important;
    font-size:14px!important;
    font-family:'Inter',sans-serif!important;
    background:#F7F8FA!important;
    transition:border-color 0.2s,box-shadow 0.2s;
}}
[data-testid="stForm"] input:focus {{
    border-color:#4D148C!important;
    box-shadow:0 0 0 3px rgba(77,20,140,0.08)!important;
    background:#FFF!important;
}}
[data-testid="stForm"] input::placeholder {{
    color:#C0C0C8!important; font-size:13px!important;
}}
[data-testid="stForm"] button[kind="formSubmit"] {{
    background:linear-gradient(135deg,#4D148C 0%,#5A1CA0 100%)!important;
    color:#FFF!important; border:none!important;
    border-radius:10px!important; font-weight:700!important;
    font-size:15px!important; font-family:'Inter',sans-serif!important;
    letter-spacing:0.4px!important; padding:12px 0!important;
    margin-top:10px!important;
    box-shadow:0 4px 14px rgba(77,20,140,0.28)!important;
    transition:all 0.2s ease!important;
}}
[data-testid="stForm"] button[kind="formSubmit"]:hover {{
    background:linear-gradient(135deg,#3C1080 0%,#4D148C 100%)!important;
    box-shadow:0 6px 20px rgba(77,20,140,0.38)!important;
    transform:translateY(-1px);
}}
[data-testid="stForm"] [data-testid="stAlert"] {{
    font-size:12px!important; padding:8px 12px!important;
    border-radius:8px!important; margin-top:6px!important;
}}

/* ── RIGHT PANEL ELEMENTS ── */
.rp {{
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    text-align:center; min-height:500px;
    position:relative; padding:40px 20px;
}}
.rp-circle {{
    position:absolute; border-radius:50%;
    border:2px solid rgba(255,255,255,0.06);
    pointer-events:none;
    top:50%; left:50%;
    transform:translate(-50%,-50%);
}}
.rp-c1 {{ width:340px; height:340px; }}
.rp-c2 {{ width:220px; height:220px; border-color:rgba(255,255,255,0.04); }}
.rp-icons {{
    display:flex; gap:14px;
    margin-bottom:28px;
    position:relative; z-index:1;
}}
.rp-ico {{
    width:48px; height:48px;
    background:rgba(255,255,255,0.12);
    border-radius:14px;
    display:flex; align-items:center; justify-content:center;
    font-size:20px;
    backdrop-filter:blur(6px);
    border:1px solid rgba(255,255,255,0.10);
}}
.rp-mock {{
    background:rgba(255,255,255,0.10);
    backdrop-filter:blur(8px);
    border:1px solid rgba(255,255,255,0.12);
    border-radius:14px;
    padding:22px 28px;
    margin-bottom:28px;
    width:260px;
    position:relative; z-index:1;
}}
.rp-bar {{
    height:8px; border-radius:4px;
    margin-bottom:10px;
}}
.rp-bar:last-child {{ margin-bottom:0; }}
.b1 {{ background:rgba(255,255,255,0.25); width:90%; }}
.b2 {{ background:rgba(255,98,0,0.50); width:70%; }}
.b3 {{ background:rgba(255,255,255,0.15); width:80%; }}
.b4 {{ background:rgba(255,98,0,0.35); width:55%; }}
.rp-h {{
    font-family:'DM Sans',sans-serif;
    font-weight:800; font-size:22px;
    color:#FFF; margin:0 0 10px;
    letter-spacing:-0.3px; line-height:1.35;
    position:relative; z-index:1;
}}
.rp-s {{
    font-family:'Inter',sans-serif;
    font-weight:400; font-size:13px;
    color:rgba(255,255,255,0.60);
    line-height:1.6; max-width:260px;
    position:relative; z-index:1;
}}
.rp-dots {{
    display:flex; gap:8px;
    margin-top:24px;
    position:relative; z-index:1;
}}
.rp-dots span {{
    width:8px; height:8px;
    border-radius:50%;
    background:rgba(255,255,255,0.25);
    display:inline-block;
}}
.rp-dots .d1 {{ background:#FF6200; }}
</style>
""", unsafe_allow_html=True)


# ── LAYOUT ───────────────────────────────────────────────────
left_col, right_col = st.columns([1.1, 1])

with left_col:
    st.markdown(f"""
        <div class="lp-logo">{_logo_tag}</div>
        <div class="lp-h">Log in to AERO</div>
        <div class="lp-sub">Welcome back! Enter your credentials to continue.</div>
        <div class="lp-div"></div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=True):
        user_id = st.text_input("User ID", placeholder="Enter your User ID", key="login_user_id")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not user_id or not password:
                st.error("❌ Please enter both User ID and Password.")
            else:
                try:
                    user = authenticate(user_id.strip(), password.strip())
                    if user:
                        login_user(user)
                        st.success(f"✓ Welcome, {user.get('display_name', user_id)}!")
                        st.balloons()
                        st.session_state.pop("login_user_id", None)
                        st.session_state.pop("login_password", None)
                        import time
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ Invalid User ID or Password. Please try again.")
                except Exception as e:
                    st.error(f"❌ Login error: {str(e)}")

    st.markdown('<div class="lp-foot">Powered by AERO &nbsp;·&nbsp; FedEx Planning &amp; Engineering</div>', unsafe_allow_html=True)

with right_col:
    st.markdown(_right_panel_html, unsafe_allow_html=True)
