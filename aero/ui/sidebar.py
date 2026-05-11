import streamlit as st


def render_sidebar(user: dict = None, **_kwargs):
    """Inject sidebar nav animation and optional user identity card."""

    st.sidebar.markdown(
        """
        <style>
        @keyframes navSlideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to   { opacity: 1; transform: translateX(0); }
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
            animation: navSlideIn 0.30s ease forwards;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(1) a { animation-delay: 0.03s; }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(2) a { animation-delay: 0.06s; }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(3) a { animation-delay: 0.09s; }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(4) a { animation-delay: 0.12s; }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(5) a { animation-delay: 0.15s; }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(6) a { animation-delay: 0.18s; }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:nth-child(7) a { animation-delay: 0.21s; }
        /* Enhanced Sidebar sign-out button styling */
        section[data-testid="stSidebar"] .fedex-signout-btn {
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
        section[data-testid="stSidebar"] .fedex-signout-btn:hover {
            background: linear-gradient(90deg, #E45528 0%, #FF6200 100%) !important;
            box-shadow: 0 4px 16px rgba(255,98,0,0.18) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
