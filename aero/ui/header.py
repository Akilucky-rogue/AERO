import streamlit as st
import base64
import os

from aero import ASSETS_DIR

_LOGO_PATH = os.path.join(ASSETS_DIR, "image.png")
try:
    with open(_LOGO_PATH, "rb") as _f:
        _LOGO_B64 = base64.b64encode(_f.read()).decode()
except Exception:
    _LOGO_B64 = ""


def render_header(title: str, subtitle: str = None, logo_width: int = 200, logo_height: int = 80, badge: str = None):
    subtitle_block = f'<div class="fedex-topbar-subtitle">{subtitle}</div>' if subtitle else ""


    # ── Right block: badge + logged-in user (only one user badge, larger size) ──
    user = st.session_state.get("aero_user")
    right_block = "<div class='fedex-topbar-right'>"
    if badge:
        right_block += f'<div class="fedex-module-badge">{badge}</div>'
    if user:
        display_name = user.get("display_name", user.get("user_id", ""))
        role = user.get("role", "")
        initials = "".join(w[0] for w in display_name.split() if w)[:2].upper() if display_name else "U"
        right_block += (
            f'<div class="fedex-user-badge fedex-user-badge-lg">'
            f'<div class="fedex-user-avatar fedex-user-avatar-lg">{initials}</div>'
            f'<div class="fedex-user-info fedex-user-info-lg">'
            f'<div class="fedex-user-name fedex-user-name-lg">{display_name}</div>'
            f'<div class="fedex-user-role fedex-user-role-lg">{role}</div>'
            f'</div></div>'
        )
    right_block += "</div>"

    if _LOGO_B64:
        logo_html = f'<img src="data:image/png;base64,{_LOGO_B64}" alt="FedEx" style="height:{logo_height}px; object-fit:contain;" />'
    else:
        logo_html = '<span class="fedex-logo-text"><span style="color:#4D148C;">Fed</span><span style="color:#FF6200;">Ex</span></span>'
    st.markdown(
        f'<div class="fedex-topbar">'
        f'<div class="fedex-topbar-left">'
        f"{logo_html}"
        f'<span class="fedex-topbar-sep"> | </span>'
        f'<div class="fedex-topbar-title-block"><div class="fedex-topbar-title">{title}</div>{subtitle_block}</div>'
        f"</div>"
        f"{right_block}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_footer(module_short: str, footer_logo_height: int = 48):
    if _LOGO_B64:
        footer_logo = f'<img src="data:image/png;base64,{_LOGO_B64}" alt="FedEx" style="height:{footer_logo_height}px; object-fit:contain;" />'
    else:
        footer_logo = '<span style="color:#4D148C;">Fed</span><span style="color:#FF6200;">Ex</span>'
    st.markdown(
        f"""
        <div class="fedex-footer">
                <div class="fedex-footer-logo">
                    {footer_logo}
                </div>
                <div class="fedex-footer-copy">
                {module_short} &nbsp;|&nbsp; AERO Platform v2.0
                &nbsp;&nbsp;&bull;&nbsp;&nbsp;
                &copy; 2026 FedEx Planning &amp; Engineering. All rights reserved.
                &nbsp;&nbsp;&bull;&nbsp;&nbsp; Confidential &amp; Proprietary
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
