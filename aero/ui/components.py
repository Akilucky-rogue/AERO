"""
components.py — Reusable UI components for the AERO application.

Provides standardised, FedEx-branded component functions to replace
inline HTML/CSS duplication across pages.
"""

import streamlit as st


# ── Brand tokens (mirror CSS vars for use in Python f-strings) ───────────────
_PURPLE = "#4D148C"
_ORANGE = "#FF6200"
_GREEN  = "#008A00"
_RED    = "#DE002E"
_YELLOW = "#FFB800"
_GREY   = "#888888"
_WHITE  = "#FFFFFF"


# ════════════════════════════════════════════════════════════════════════════
# KPI CARD  — the single source of truth for metric tiles across all pages
# ════════════════════════════════════════════════════════════════════════════

def render_kpi_card(
    col,
    label: str,
    value: str,
    color: str = _PURPLE,
    subtitle: str = None,
    icon: str = None,
):
    """Render a branded KPI tile into a Streamlit column.

    Parameters
    ----------
    col       : st.column — the column to render into
    label     : str       — upper-label text (auto-uppercased)
    value     : str       — the large number / text value
    color     : str       — hex accent colour (left border + value colour)
    subtitle  : str|None  — optional small line below the value
    icon      : str|None  — optional emoji/icon before the value
    """
    icon_html = f'<span style="font-size:16px;margin-right:6px;">{icon}</span>' if icon else ""
    sub_html  = (
        f'<div style="font-size:10px;color:#999;font-weight:600;margin-top:3px;'
        f'letter-spacing:0.4px;">{subtitle}</div>'
        if subtitle else ""
    )
    col.markdown(f"""
    <div style="
        background:#FFFFFF;
        border-left:4px solid {color};
        border-radius:8px;
        padding:14px 14px 12px;
        box-shadow:0 1px 4px rgba(0,0,0,0.07);
        transition:box-shadow .15s ease,transform .15s ease;
    " onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 14px rgba(0,0,0,0.11)'"
       onmouseout="this.style.transform='';this.style.boxShadow='0 1px 4px rgba(0,0,0,0.07)'">
        <div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;
            letter-spacing:0.9px;margin-bottom:6px;">{label}</div>
        <div style="font-size:24px;font-weight:800;color:{color};line-height:1.1;">
            {icon_html}{value}
        </div>
        {sub_html}
    </div>""", unsafe_allow_html=True)


def render_kpi_row(items: list):
    """Render a full row of KPI cards from a list.

    Parameters
    ----------
    items : list of dicts with keys: label, value, color (opt), subtitle (opt), icon (opt)

    Example
    -------
    render_kpi_row([
        {"label": "Total Records", "value": "57,237", "color": _PURPLE},
        {"label": "NSL On-Time",   "value": "60.8%",  "color": _GREEN},
    ])
    """
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        render_kpi_card(
            col,
            label    = item["label"],
            value    = item["value"],
            color    = item.get("color", _PURPLE),
            subtitle = item.get("subtitle"),
            icon     = item.get("icon"),
        )


# ════════════════════════════════════════════════════════════════════════════
# INFO BANNER  — instruction / context banners at the top of tabs
# ════════════════════════════════════════════════════════════════════════════

def render_info_banner(title: str, body: str, accent: str = _PURPLE):
    """Render a branded instruction banner.

    Parameters
    ----------
    title  : str — bold heading
    body   : str — HTML-safe body text (can include <b> tags)
    accent : str — left-border / title colour
    """
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#F7F3FF 0%,#FFFFFF 100%);
        border-left:5px solid {accent};
        border-radius:10px;
        padding:16px 20px;
        margin-bottom:20px;
        box-shadow:0 1px 3px rgba(0,0,0,0.06);
    ">
        <div style="font-weight:800;color:#1A1A1A;font-size:13px;
            text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
            {title}
        </div>
        <div style="color:#555;font-size:13px;line-height:1.65;">
            {body}
        </div>
    </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# MODULE CARD  — homepage & overview module tiles
# ════════════════════════════════════════════════════════════════════════════

def render_module_card(
    col,
    icon: str,
    title: str,
    description: str,
    accent: str = _PURPLE,
    gradient: bool = False,
):
    """Render a module overview card (used on home page and dashboards).

    Parameters
    ----------
    gradient : bool — if True, renders with a coloured gradient background
                       (for featured/primary modules); otherwise plain white.
    """
    if gradient:
        bg   = f"linear-gradient(135deg,{accent} 0%,{accent}CC 100%)"
        text = "#FFFFFF"
        sub  = "rgba(255,255,255,0.80)"
        bdr  = "none"
    else:
        bg   = "#FFFFFF"
        text = "#1A1A1A"
        sub  = "#565656"
        bdr  = f"1px solid #E3E3E3; border-top:4px solid {accent}"

    col.markdown(f"""
    <div style="
        background:{bg};
        border:{bdr};
        border-radius:12px;
        padding:1.25rem;
        box-shadow:0 2px 8px rgba(0,0,0,0.07);
        height:100%;
        transition:transform .15s ease,box-shadow .15s ease;
    " onmouseover="this.style.transform='translateY(-3px)';this.style.boxShadow='0 6px 20px rgba(0,0,0,0.12)'"
       onmouseout="this.style.transform='';this.style.boxShadow='0 2px 8px rgba(0,0,0,0.07)'">
        <div style="font-size:26px;margin-bottom:8px;">{icon}</div>
        <div style="font-size:14px;font-weight:800;color:{text};
            margin-bottom:6px;letter-spacing:-0.2px;">{title}</div>
        <div style="font-size:12px;color:{sub};line-height:1.6;">{description}</div>
    </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# STEP GUIDE  — numbered process flow cards
# ════════════════════════════════════════════════════════════════════════════

def render_step_guide(steps: list, accent: str = _PURPLE):
    """Render a numbered step-by-step guide.

    Parameters
    ----------
    steps : list of dicts with keys: title, description
    """
    st.markdown(f"""
    <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:12px;
        padding:1.5rem;margin-bottom:1rem;box-shadow:0 1px 4px rgba(0,0,0,0.07);">
        <div style="font-size:13px;font-weight:700;color:{accent};
            text-transform:uppercase;letter-spacing:0.6px;margin-bottom:14px;">
            Process Flow
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
    """, unsafe_allow_html=True)

    for i, step in enumerate(steps):
        border = "border-bottom:1px solid #F0F0F0;" if i < len(steps) - 1 else ""
        st.markdown(f"""
        <tr style="{border}">
            <td style="padding:9px 12px;font-weight:800;color:{accent};
                width:36px;vertical-align:top;font-size:15px;">{i+1}</td>
            <td style="padding:9px 12px;font-weight:700;color:#333;
                width:200px;vertical-align:top;">{step['title']}</td>
            <td style="padding:9px 12px;color:#565656;line-height:1.6;">
                {step['description']}</td>
        </tr>""", unsafe_allow_html=True)

    st.markdown("</table></div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# LEGACY COMPONENTS (kept for backward compat with health_monitor.py)
# ════════════════════════════════════════════════════════════════════════════

def render_section_header(title, icon="📋", gradient_end="#F3E8FF", border_color="#4D148C"):
    """Render a gradient section header banner."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #FFFFFF 0%, {gradient_end} 100%);
        border-left: 6px solid {border_color};
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 16px;
    ">
        <div style="font-weight: 700; color: #333333; font-size: 16px;">{icon} {title}</div>
    </div>
    """, unsafe_allow_html=True)


def render_status_cards(summary, card_height="height:120px; min-height:85px;"):
    """Render the standard 4-column health status cards (Healthy / Review / Critical / Most Affected)."""
    base_style = (
        f"{card_height} box-sizing:border-box; display:flex; flex-direction:column; "
        "justify-content:center; align-items:center; padding:8px;"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background:#ECFDF5;border:1px solid #E6F4E6;border-radius:8px;
            text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{base_style}">
            <div style="font-size:20px;margin-bottom:4px;">✅</div>
            <div style="color:#047857;font-weight:700;font-size:20px;">{summary['healthy_count']}</div>
            <div style="color:#059669;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Healthy</div>
            <div style="color:#065f46;font-size:11px;margin-top:6px;font-weight:600;">Range: 0-10%</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background:#FFFBEB;border:1px solid #FEE3C3;border-radius:8px;
            text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{base_style}">
            <div style="font-size:20px;margin-bottom:4px;">⚠️</div>
            <div style="color:#D97706;font-weight:700;font-size:20px;">{summary['review_needed_count']}</div>
            <div style="color:#B45309;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Review</div>
            <div style="color:#92400e;font-size:11px;margin-top:6px;font-weight:600;">Range: 10-20%</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;
            text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{base_style}">
            <div style="font-size:20px;margin-bottom:4px;">🚨</div>
            <div style="color:#DC2626;font-weight:700;font-size:20px;">{summary['critical_count']}</div>
            <div style="color:#991B1B;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Critical</div>
            <div style="color:#7f1d1d;font-size:11px;margin-top:6px;font-weight:600;">Range: &gt;20%</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        most_affected = summary.get('most_affected')
        if most_affected:
            emoji = most_affected.get('emoji', '❓')
            loc   = most_affected.get('loc_id', 'N/A')
            dev   = most_affected.get('deviation_percent', 0)
            st.markdown(f"""
            <div style="background:#FFF7F7;border:1px solid #FECACA;border-radius:8px;
                text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{base_style}">
                <div style="font-size:20px;margin-bottom:4px;">{emoji}</div>
                <div style="color:#333;font-weight:700;font-size:16px;">{loc}</div>
                <div style="color:#991B1B;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Most Affected</div>
                <div style="color:#991B1B;font-size:11px;margin-top:4px;font-weight:600;">Max Deviation: {dev:+.1f}%</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#F2F2F2;border:1px solid #D1D5DB;border-radius:8px;
                text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{base_style}">
                <div style="font-size:20px;margin-bottom:4px;">✅</div>
                <div style="color:#333;font-weight:700;font-size:16px;">All Stations Sufficient</div>
                <div style="color:#565656;font-size:11px;font-weight:600;margin-top:6px;">No negative deviations found</div>
            </div>""", unsafe_allow_html=True)


def render_coming_soon_page(title, icon, description, phase_label, features):
    """Render a standardised 'Coming Soon' placeholder page."""
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#F5F5F5 0%,#FFFFFF 100%);
        border-radius:16px;padding:3rem 2rem;margin:2rem 0;
        text-align:center;border:2px dashed #C8C8C8;">
        <div style="font-size:56px;margin-bottom:1rem;">{icon}</div>
        <h2 style="color:#4D148C;margin:0 0 0.5rem;font-weight:800;font-size:22px;">
            {title} — Coming Soon</h2>
        <p style="color:#565656;font-size:14px;max-width:520px;margin:0 auto;line-height:1.7;">
            {description}</p>
        <div style="margin-top:1.5rem;">
            <span style="background:rgba(77,20,140,0.08);color:#4D148C;
                padding:6px 16px;border-radius:100px;font-size:12px;font-weight:600;">
                {phase_label}</span>
        </div>
    </div>""", unsafe_allow_html=True)

    if features:
        cols = st.columns(len(features))
        for col, (feat_icon, feat_title, feat_desc) in zip(cols, features):
            with col:
                st.markdown(f"""
                <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:12px;
                    padding:1.25rem;text-align:center;min-height:160px;">
                    <div style="font-size:28px;margin-bottom:0.75rem;">{feat_icon}</div>
                    <div style="font-weight:700;font-size:13px;color:#4D148C;margin-bottom:0.5rem;">
                        {feat_title}</div>
                    <div style="color:#565656;font-size:12px;line-height:1.5;">{feat_desc}</div>
                </div>""", unsafe_allow_html=True)
