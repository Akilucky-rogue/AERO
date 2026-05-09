"""
components.py — Reusable UI components for the AERO application.

Provides standardized, FedEx-branded component functions to replace
inline HTML/CSS duplication across pages.
"""

import streamlit as st


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
    """Render the standard 4-column health status cards (Healthy / Review / Critical / Most Affected).

    Parameters
    ----------
    summary : dict
        Output of ``get_summary_stats()`` containing healthy_count, review_needed_count,
        critical_count, and most_affected.
    card_height : str
        CSS height snippet for card sizing.
    """
    base_style = (
        f"{card_height} box-sizing:border-box; display:flex; flex-direction:column; "
        "justify-content:center; align-items:center; padding:8px;"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="
            background: #ECFDF5; border: 1px solid #E6F4E6;
            border-radius: 8px; text-align: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04); {base_style}
        ">
            <div style="font-size:20px; margin-bottom:4px;">✅</div>
            <div style="color:#047857; font-weight:700; font-size:20px;">{summary['healthy_count']}</div>
            <div style="color:#059669; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Healthy</div>
            <div style="color:#065f46; font-size:11px; margin-top:6px; font-weight:600;">Range: 0-10%</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="
            background: #FFFBEB; border: 1px solid #FEE3C3;
            border-radius: 8px; text-align: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04); {base_style}
        ">
            <div style="font-size:20px; margin-bottom:4px;">⚠️</div>
            <div style="color:#D97706; font-weight:700; font-size:20px;">{summary['review_needed_count']}</div>
            <div style="color:#B45309; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Review</div>
            <div style="color:#92400e; font-size:11px; margin-top:6px; font-weight:600;">Range: 10-20%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="
            background: #FEF2F2; border: 1px solid #FECACA;
            border-radius: 8px; text-align: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04); {base_style}
        ">
            <div style="font-size:20px; margin-bottom:4px;">🚨</div>
            <div style="color:#DC2626; font-weight:700; font-size:20px;">{summary['critical_count']}</div>
            <div style="color:#991B1B; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Critical</div>
            <div style="color:#7f1d1d; font-size:11px; margin-top:6px; font-weight:600;">Range: &gt;20%</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        most_affected = summary.get('most_affected')
        if most_affected:
            emoji = most_affected.get('emoji', '❓')
            loc = most_affected.get('loc_id', 'N/A')
            dev = most_affected.get('deviation_percent', 0)
            st.markdown(f"""
            <div style="
                background: #FFF7F7; border: 1px solid #FECACA;
                border-radius: 8px; text-align: center;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04); {base_style}
            ">
                <div style="font-size:20px; margin-bottom:4px;">{emoji}</div>
                <div style="color:#333333; font-weight:700; font-size:16px;">{loc}</div>
                <div style="color:#991B1B; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Most Affected</div>
                <div style="color:#991B1B; font-size:11px; margin-top:4px; font-weight:600;">Max Deviation: {dev:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="
                background: #F2F2F2; border: 1px solid #D1D5DB;
                border-radius: 8px; text-align: center;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04); {base_style}
            ">
                <div style="font-size:20px; margin-bottom:4px;">✅</div>
                <div style="color:#333333; font-weight:700; font-size:16px;">All Stations Sufficient</div>
                <div style="color:#565656; font-size:11px; font-weight:600; margin-top:6px;">No negative deviations found</div>
            </div>
            """, unsafe_allow_html=True)


def render_coming_soon_page(title, icon, description, phase_label, features):
    """Render a standardized 'Coming Soon' placeholder page.

    Parameters
    ----------
    title : str
        Module title (e.g. "Gateway Operations").
    icon : str
        Emoji for the hero section.
    description : str
        One-paragraph description of the upcoming module.
    phase_label : str
        Phase tag text (e.g. "Phase 2 Integration").
    features : list[tuple[str, str, str]]
        List of (emoji, title, description) tuples for feature cards.
    """
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, var(--gray-10) 0%, #FFFFFF 100%);
        border-radius: 16px;
        padding: 3rem 2rem;
        margin: 2rem 0;
        text-align: center;
        border: 2px dashed var(--gray-30);
    ">
        <div style="font-size: 56px; margin-bottom: 1rem;">{icon}</div>
        <h2 style="color: var(--fc-purple); margin: 0 0 0.5rem 0; font-weight: 800; font-size: 22px;">{title} — Coming Soon</h2>
        <p style="color: var(--gray-70); font-size: 14px; max-width: 520px; margin: 0 auto; line-height: 1.7;">
            {description}
        </p>
        <div style="margin-top: 1.5rem;">
            <span style="background: rgba(77,20,140,0.08); color: var(--fc-purple); padding: 6px 16px; border-radius: 100px; font-size: 12px; font-weight: 600;">{phase_label}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if features:
        cols = st.columns(len(features))
        for col, (feat_icon, feat_title, feat_desc) in zip(cols, features):
            with col:
                st.markdown(f"""
                <div style="
                    background: #FFFFFF;
                    border: 1px solid var(--gray-20);
                    border-radius: 12px;
                    padding: 1.25rem;
                    text-align: center;
                    min-height: 160px;
                ">
                    <div style="font-size: 28px; margin-bottom: 0.75rem;">{feat_icon}</div>
                    <div style="font-weight: 700; font-size: 13px; color: var(--fc-purple); margin-bottom: 0.5rem;">{feat_title}</div>
                    <div style="color: var(--gray-70); font-size: 12px; line-height: 1.5;">{feat_desc}</div>
                </div>
                """, unsafe_allow_html=True)
