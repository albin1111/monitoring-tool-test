import streamlit as st
from pathlib import Path
import base64

st.set_page_config(
    page_title="SBC Data Management and Reporting",
    layout="wide",
    page_icon="assets/sbc_logo.png",
)

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "sbc_logo.png"

if LOGO_PATH.exists():
    logo_base64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()

    with st.sidebar:
        st.markdown(
            f"""
            <div style="
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                padding: 8px 0 20px 0;
            ">
                <img
                    src="data:image/png;base64,{logo_base64}"
                    style="
                        width: 90px;
                        height: 90px;
                        object-fit: contain;
                    "
                >
                <div style="
                    font-size: 20px;
                    font-weight: 700;
                    line-height: 1.15;
                    text-align: left;
                ">
                    SBC<br>Data Management<br>
                    and Reporting
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.sidebar.error(f"Logo not found: {LOGO_PATH}")

from page.Upload import renderupload
from page.Consolidated_Data import renderconso
from page.Dashboard import renderdashboard
from page.extractor.drr_extractor import renderdrrextractor
from page.extractor.ptp_kept_extractor import renderptpkeptextractor
from page.extractor.active_extractor import renderactiveextractor
from page.report.DAR import render_dar
from components.sidebar import sidebar


# ============================================================
# PERSISTENT APPLICATION STATE
# ============================================================

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

if "selected_campaign" not in st.session_state:
    st.session_state.selected_campaign = None

if "selected_month" not in st.session_state:
    st.session_state.selected_month = None

if "selected_file_type" not in st.session_state:
    st.session_state.selected_file_type = None

if "selected_report" not in st.session_state:
    st.session_state.selected_report = None

if "selected_extraction" not in st.session_state:
    st.session_state.selected_extraction = None


# ============================================================
# NAVIGATION
# ============================================================

def navigate(page_name):
    st.session_state.current_page = page_name
    st.rerun()


# ============================================================
# REPORT OPTIONS
# ============================================================

REPORT_OPTIONS = [
    "Loans Tracker",
    "KPI Monitoring",
    "LSAL Account Status",
    "NPL Prio List",
    "Agency Performance Monitoring",
]


# ============================================================
# DASHBOARD
# ============================================================

if st.sidebar.button(
    "Dashboard",
    use_container_width=True,
    key="nav_dashboard",
):
    navigate("Dashboard")


# ============================================================
# INGEST AND CONSOLIDATE
# ============================================================

st.sidebar.markdown("### Ingest and Consolidate")

if st.sidebar.button(
    "Upload Data",
    use_container_width=True,
    key="nav_upload",
):
    navigate("Upload Data")

if st.sidebar.button(
    "Consolidator",
    use_container_width=True,
    key="nav_consolidator",
):
    navigate("Consolidator")


# ============================================================
# REPORTING / EXTRACTION DROPDOWNS
# ============================================================

sidebar()


# ============================================================
# CURRENT PAGE
# ============================================================

st.sidebar.markdown("---")

st.sidebar.caption(
    f"Current page: {st.session_state.current_page}"
)

if st.session_state.selected_report:
    st.sidebar.caption(
        f"Selected report: {st.session_state.selected_report}"
    )


# ============================================================
# PAGE ROUTING
# ============================================================

if st.session_state.current_page == "Upload Data":
    renderupload()

elif st.session_state.current_page == "Consolidator":
    renderconso()

elif st.session_state.current_page == "Dashboard":
    renderdashboard()

elif st.session_state.current_page == "DRR Extractor":
    renderdrrextractor()

elif st.session_state.current_page == "PTP and KEPT Extractor":
    renderptpkeptextractor()

elif st.session_state.current_page == "Active Extractor":
    renderactiveextractor()
    
elif st.session_state.current_page == "DAR":
    render_dar()

else:

    st.error(
        f"Page '{st.session_state.current_page}' "
        f"is not currently implemented."
    )

    st.session_state.current_page = "Dashboard"
    st.rerun()