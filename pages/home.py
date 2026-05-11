import streamlit as st
import pandas as pd
import io
from aero.ui.header import render_header, render_footer
from aero.auth.service import get_current_user

# ── Role detection ───────────────────────────────────────────────────────────
_user = get_current_user()
_role = (_user.get("role", "") if _user else "")

# ============================================================
# LEADERSHIP — dedicated overview page (no emojis)
# ============================================================
if _role == "Leadership":
    render_header(
        "EXECUTIVE DASHBOARD",
        "Leadership Analytics | FedEx Planning & Engineering",
        logo_height=80,
        badge="LEADERSHIP",
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#FAFAFA 0%,#FFFFFF 100%);
        border-left:5px solid #4D148C;border-radius:8px;padding:1.2rem 1.5rem;
        margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,0.07);">
        <div style="font-weight:700;color:#1A1A1A;font-size:17px;
            text-transform:uppercase;letter-spacing:0.3px;margin-bottom:6px;">
            About the Executive Dashboard
        </div>
        <p style="color:#555;font-size:13px;line-height:1.7;margin:0;">
            The Executive Dashboard provides a consolidated, read-only view of
            operational health and performance analytics across all FedEx divisions.
            Select a division tab in the <strong>Executive Dashboard</strong> page to
            view its dedicated report. Each tab is fully independent — data from one
            division does not affect another.
        </p>
    </div>""", unsafe_allow_html=True)

    # Division overview cards
    st.markdown("""
    <div style="font-weight:700;color:#333;font-size:13px;text-transform:uppercase;
        letter-spacing:0.6px;margin-bottom:10px;">Division Overview</div>""",
        unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-top:4px solid #4D148C;
            border-radius:10px;padding:1.1rem 1.25rem;box-shadow:0 1px 4px rgba(0,0,0,0.07);min-height:160px;">
            <div style="font-size:12px;font-weight:800;color:#4D148C;text-transform:uppercase;
                letter-spacing:0.7px;margin-bottom:8px;border-bottom:1px solid #F0E8FF;
                padding-bottom:6px;">Station / Hub</div>
            <p style="font-size:12px;color:#555;line-height:1.65;margin:0;">
                Displays health status reports published by Facility teams across
                Stations and Hubs. Covers Area, Resource, and Courier monitoring
                with breakdown by Healthy, Review, and Critical classifications.
                Volume trend charts and critical-location tables are also available.
            </p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-top:4px solid #1A5276;
            border-radius:10px;padding:1.1rem 1.25rem;box-shadow:0 1px 4px rgba(0,0,0,0.07);min-height:160px;">
            <div style="font-size:12px;font-weight:800;color:#1A5276;text-transform:uppercase;
                letter-spacing:0.7px;margin-bottom:8px;border-bottom:1px solid #E8F4FB;
                padding-bottom:6px;">Gateway</div>
            <p style="font-size:12px;color:#555;line-height:1.65;margin:0;">
                Will present inter-hub linehaul and air gateway performance metrics
                once Phase 2 integration is complete. Covers on-time departure,
                linehaul utilization, gateway volume, cross-dock efficiency, and
                route-level performance benchmarks.
            </p>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-top:4px solid #7B241C;
            border-radius:10px;padding:1.1rem 1.25rem;box-shadow:0 1px 4px rgba(0,0,0,0.07);min-height:160px;">
            <div style="font-size:12px;font-weight:800;color:#7B241C;text-transform:uppercase;
                letter-spacing:0.7px;margin-bottom:8px;border-bottom:1px solid #FDECEA;
                padding-bottom:6px;">Services</div>
            <p style="font-size:12px;color:#555;line-height:1.65;margin:0;">
                Will present SLA compliance, customer contact volume,
                and first-attempt delivery rates once Phase 2 integration is complete.
                Covers service failure categorization and NPS integration
                across all service types and station divisions.
            </p>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Navigation guidance
    st.markdown("""
    <div style="background:linear-gradient(135deg,#FAFAFA 0%,#FFFFFF 100%);
        border-left:5px solid #FF6200;border-radius:8px;padding:1.1rem 1.5rem;
        box-shadow:0 1px 4px rgba(0,0,0,0.07);">
        <div style="font-weight:700;color:#1A1A1A;font-size:13px;text-transform:uppercase;
            letter-spacing:0.5px;margin-bottom:10px;">How to Navigate</div>
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <tr style="border-bottom:1px solid #F0F0F0;">
                <td style="padding:7px 10px;font-weight:700;color:#4D148C;
                    width:32px;vertical-align:top;">1</td>
                <td style="padding:7px 10px;font-weight:600;color:#333;
                    width:190px;vertical-align:top;">Open Executive Dashboard</td>
                <td style="padding:7px 10px;color:#555;">
                    Select <strong>Executive Dashboard</strong> from the left navigation panel
                    to open the main analytics page.</td>
            </tr>
            <tr style="border-bottom:1px solid #F0F0F0;">
                <td style="padding:7px 10px;font-weight:700;color:#4D148C;vertical-align:top;">2</td>
                <td style="padding:7px 10px;font-weight:600;color:#333;vertical-align:top;">Select Division Tab</td>
                <td style="padding:7px 10px;color:#555;">
                    Choose from <strong>STATION / HUB</strong>, <strong>GATEWAY</strong>, or
                    <strong>SERVICES</strong> tabs at the top of the page. Each tab is
                    independently scoped to its division.</td>
            </tr>
            <tr>
                <td style="padding:7px 10px;font-weight:700;color:#4D148C;vertical-align:top;">3</td>
                <td style="padding:7px 10px;font-weight:600;color:#333;vertical-align:top;">Review the Report</td>
                <td style="padding:7px 10px;color:#555;">
                    Station / Hub data populates automatically from published Facility health
                    reports. Gateway and Services tabs will activate in Phase 2.</td>
            </tr>
        </table>
    </div>""", unsafe_allow_html=True)

    render_footer("LEADERSHIP")
    st.stop()

# ============================================================
# ALL OTHER ROLES — standard home page
# ============================================================
render_header(
    "AERO - Automated Evaluation Of Resource Occupancy",
    "FedEx Planning & Engineering | AREA, RESOURCE & COURIER PLANNING",
    logo_height=80,
)

# ============================================================
# PROCESS FLOW GUIDELINES
# ============================================================
st.markdown("""
<div style="
    background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
    border-left: 4px solid #4D148C;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin: 0 0 1.5rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
">
    <h3 style="color: #333333; margin: 0; font-size: 18px; font-weight: 700; font-family:'DM Sans','Inter',sans-serif;">📋 How to Use AERO</h3>
    <p style="color: #565656; font-size: 13px; margin: 4px 0 0 0; font-family:'Inter',sans-serif;">Follow the steps below to get started with facility planning and health monitoring</p>
</div>
""", unsafe_allow_html=True)

# Step-by-step guide
st.markdown("""
<div style="
    background: #FFFFFF;
    border: 1px solid #E3E3E3;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    font-family:'Inter','DM Sans',sans-serif;
">
    <div style="font-size: 15px; font-weight: 700; color: #4D148C; margin-bottom: 12px;">🔄 Process Flow</div>
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
        <tr style="border-bottom:1px solid #EEE;">
            <td style="padding:8px 12px; font-weight:700; color:#4D148C; width:40px; vertical-align:top;">1</td>
            <td style="padding:8px 12px; font-weight:600; color:#333; width:200px; vertical-align:top;">Prepare Data Files</td>
            <td style="padding:8px 12px; color:#565656;">Download the Excel templates below and populate them with your FAMIS volume data and Facility Master data. Ensure <code>loc_id</code> and <code>date</code> columns are filled correctly.</td>
        </tr>
        <tr style="border-bottom:1px solid #EEE;">
            <td style="padding:8px 12px; font-weight:700; color:#4D148C; vertical-align:top;">2</td>
            <td style="padding:8px 12px; font-weight:600; color:#333; vertical-align:top;">Upload to Health Monitor</td>
            <td style="padding:8px 12px; color:#565656;">Navigate to <b>Health Monitoring → Health Monitor</b>. Upload both the FAMIS file and the Facility Master file using the file uploaders at the top of the page.</td>
        </tr>
        <tr style="border-bottom:1px solid #EEE;">
            <td style="padding:8px 12px; font-weight:700; color:#4D148C; vertical-align:top;">3</td>
            <td style="padding:8px 12px; font-weight:600; color:#333; vertical-align:top;">Select File Type & Date</td>
            <td style="padding:8px 12px; color:#565656;">Choose the FAMIS file type (Daily / Weekly / Monthly) for volume normalization. Then select the date to analyze from the dropdown.</td>
        </tr>
        <tr style="border-bottom:1px solid #EEE;">
            <td style="padding:8px 12px; font-weight:700; color:#4D148C; vertical-align:top;">4</td>
            <td style="padding:8px 12px; font-weight:600; color:#333; vertical-align:top;">Review Health Tabs</td>
            <td style="padding:8px 12px; color:#565656;">Switch between <b>Area Monitor</b>, <b>Station Agent Monitor</b>, <b>Courier Monitor</b>, and <b>Analytics</b> tabs to review health status across all stations.</td>
        </tr>
        <tr style="border-bottom:1px solid #EEE;">
            <td style="padding:8px 12px; font-weight:700; color:#4D148C; vertical-align:top;">5</td>
            <td style="padding:8px 12px; font-weight:600; color:#333; vertical-align:top;">Publish Reports</td>
            <td style="padding:8px 12px; color:#565656;">At the bottom of the Health Monitor page, use <b>Publish to Excel</b> to download reports or <b>Publish to Database</b> to store results in the central database.</td>
        </tr>
        <tr>
            <td style="padding:8px 12px; font-weight:700; color:#4D148C; vertical-align:top;">6</td>
            <td style="padding:8px 12px; font-weight:600; color:#333; vertical-align:top;">Individual Trackers</td>
            <td style="padding:8px 12px; color:#565656;">Use the <b>Area Tracker</b>, <b>Resource Tracker</b>, and <b>Courier Tracker</b> pages for detailed single-station calculations. These auto-populate volumes from uploaded FAMIS data.</td>
        </tr>
    </table>
</div>
""", unsafe_allow_html=True)

# ============================================================
# MODULE OVERVIEW CARDS
# ============================================================
st.markdown("""
<div style="
    background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
    border-left: 4px solid #FF6200;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin: 1rem 0 1rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
">
    <h3 style="color: #333333; margin: 0; font-size: 18px; font-weight: 700; font-family:'DM Sans','Inter',sans-serif;">📦 Modules</h3>
</div>
""", unsafe_allow_html=True)

nav_col1, nav_col2, nav_col3 = st.columns(3)

with nav_col1:
    st.markdown("""
    <div style="background:#FFF;border:1px solid #E3E3E3;border-radius:12px;padding:1.25rem;box-shadow:0 1px 3px rgba(0,0,0,0.08);height:100%;">
        <div style="font-size:22px;margin-bottom:0.5rem;">🏢</div>
        <div style="font-size:15px;font-weight:700;color:#333;margin-bottom:0.35rem;font-family:'DM Sans',sans-serif;">Area Tracker</div>
        <div style="font-size:12px;color:#565656;font-family:'Inter',sans-serif;">Calculate facility area requirements: sorting, equipment, caging & supplies based on volume and model type</div>
    </div>
    """, unsafe_allow_html=True)

with nav_col2:
    st.markdown("""
    <div style="background:#FFF;border:1px solid #E3E3E3;border-radius:12px;padding:1.25rem;box-shadow:0 1px 3px rgba(0,0,0,0.08);height:100%;">
        <div style="font-size:22px;margin-bottom:0.5rem;">👥</div>
        <div style="font-size:15px;font-weight:700;color:#333;margin-bottom:0.35rem;font-family:'DM Sans',sans-serif;">Resource Tracker</div>
        <div style="font-size:12px;color:#565656;font-family:'Inter',sans-serif;">Calculate General OSA, LASA, Dispatcher & Trace Agent requirements for a station</div>
    </div>
    """, unsafe_allow_html=True)

with nav_col3:
    st.markdown("""
    <div style="background:#FFF;border:1px solid #E3E3E3;border-radius:12px;padding:1.25rem;box-shadow:0 1px 3px rgba(0,0,0,0.08);height:100%;">
        <div style="font-size:22px;margin-bottom:0.5rem;">🚚</div>
        <div style="font-size:15px;font-weight:700;color:#333;margin-bottom:0.35rem;font-family:'DM Sans',sans-serif;">Courier Tracker</div>
        <div style="font-size:12px;color:#565656;font-family:'Inter',sans-serif;">Compute courier headcount requirements based on stops, productivity and absenteeism</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

nav_col4, nav_col5 = st.columns(2)

with nav_col4:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#4D148C 0%,#671CAA 100%);border-radius:12px;padding:1.25rem;box-shadow:0 4px 12px rgba(77,20,140,0.25);height:100%;">
        <div style="font-size:22px;margin-bottom:0.5rem;">📊</div>
        <div style="font-size:15px;font-weight:700;color:#FFF;margin-bottom:0.35rem;font-family:'DM Sans',sans-serif;">Health Monitor</div>
        <div style="font-size:12px;color:rgba(255,255,255,0.8);font-family:'Inter',sans-serif;">Upload FAMIS + Master data to analyze Area, Resource & Courier health across all stations. Publish results to Excel or the central database.</div>
    </div>
    """, unsafe_allow_html=True)

with nav_col5:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#FF6200 0%,#FF8533 100%);border-radius:12px;padding:1.25rem;box-shadow:0 4px 12px rgba(255,98,0,0.25);height:100%;">
        <div style="font-size:22px;margin-bottom:0.5rem;">⚙️</div>
        <div style="font-size:15px;font-weight:700;color:#FFF;margin-bottom:0.35rem;font-family:'DM Sans',sans-serif;">User Controls</div>
        <div style="font-size:12px;color:rgba(255,255,255,0.8);font-family:'Inter',sans-serif;">Configure global parameters, thresholds and model settings that drive all calculations across the application.</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# DOWNLOADABLE EXCEL TEMPLATES
# ============================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="
    background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
    border-left: 4px solid #4D148C;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin: 0 0 1rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
">
    <h3 style="color: #333333; margin: 0; font-size: 18px; font-weight: 700; font-family:'DM Sans','Inter',sans-serif;">📥 Download Excel Templates</h3>
    <p style="color: #565656; font-size: 13px; margin: 4px 0 0 0; font-family:'Inter',sans-serif;">Use these templates to prepare your data for upload into the Health Monitor</p>
</div>
""", unsafe_allow_html=True)

dl_col1, dl_col2 = st.columns(2)

with dl_col1:
    st.markdown("**FAMIS / Volume Data Template**")
    st.caption("Columns: date, loc_id, pk_gross_tot, pk_gross_inb, pk_gross_outb, pk_oda, pk_opa, pk_roc, fte_tot, st_cr_or, st_h_or, pk_st_or, pk_fte, pk_cr_or")
    famis_template = pd.DataFrame(columns=[
        'date', 'loc_id', 'pk_gross_tot', 'pk_gross_inb', 'pk_gross_outb',
        'pk_oda', 'pk_opa', 'pk_roc', 'fte_tot', 'st_cr_or', 'st_h_or',
        'pk_st_or', 'pk_fte', 'pk_cr_or'
    ])
    # Add a sample row
    famis_template.loc[0] = ['2025-01-01', 'ABCD', 1000, 600, 400, 50, 30, 200, 10, 2.0, 8.0, 1.5, 100, 2.5]

    buf_famis = io.BytesIO()
    with pd.ExcelWriter(buf_famis, engine='openpyxl') as writer:
        famis_template.to_excel(writer, index=False, sheet_name='FAMIS')
    buf_famis.seek(0)

    st.download_button(
        label="⬇️  Download FAMIS Template",
        data=buf_famis.getvalue(),
        file_name="FAMIS_Template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with dl_col2:
    st.markdown("**Facility Master Data Template**")
    st.caption("Columns: date, loc_id, total_facility_area, ops_area, current_total_osa, current_total_couriers")
    master_template = pd.DataFrame(columns=[
        'date', 'loc_id', 'total_facility_area', 'ops_area',
        'current_total_osa', 'current_total_couriers'
    ])
    master_template.loc[0] = ['2025-01-01', 'ABCD', 50000, 35000, 25.0, 12]

    buf_master = io.BytesIO()
    with pd.ExcelWriter(buf_master, engine='openpyxl') as writer:
        master_template.to_excel(writer, index=False, sheet_name='Master')
    buf_master.seek(0)

    st.download_button(
        label="⬇️  Download Master Template",
        data=buf_master.getvalue(),
        file_name="Master_Template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# Footer
render_footer("HOME")
