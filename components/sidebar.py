import streamlit as st


# ============================================================
# OPTIONS
# ============================================================

REPORTING_OPTIONS = [
    "",
    "DAR",
    "PTP Tracker",
    "KPI Monitoring",
    "Loans Tracker",
]

EXTRACTION_OPTIONS = [
    "",
    "DRR Extractor",
    "PTP and KEPT Extractor",
    "Active Extractor",
    "Leads Extractor",
]


# ============================================================
# CALLBACKS
# ============================================================

def clear_selectors():
    """
    Reset both dropdowns whenever a new module is selected.
    """
    st.session_state.reporting_selector = ""
    st.session_state.extraction_selector = ""


def update_page():
    """
    Switch the active page and blank the other dropdown.
    """
    reporting = st.session_state.get(
        "reporting_selector",
        "",
    )
    extraction = st.session_state.get(
        "extraction_selector",
        "",
    )

    selected = reporting or extraction

    if not selected:
        return

    if st.session_state.current_page == selected:
        return

    st.session_state.current_page = selected

    # Reset both selectors so only the active menu shows a value.
    clear_selectors()


# ============================================================
# SIDEBAR
# ============================================================

def sidebar():
    with st.sidebar:

        # ====================================================
        # REPORTING
        # ====================================================

        st.markdown("### Reporting")

        st.selectbox(
            "Select Report",
            REPORTING_OPTIONS,
            key="reporting_selector",
            on_change=update_page,
        )

        # ====================================================
        # EXTRACTION
        # ====================================================

        st.markdown("### Extraction")

        st.selectbox(
            "Select Extraction",
            EXTRACTION_OPTIONS,
            key="extraction_selector",
            on_change=update_page,
        )
