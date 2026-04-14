import streamlit as st
import pandas as pd
import io
from aero.ui.header import render_header, render_footer

# Apply global styles

# Render shared header (logo + title)
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
