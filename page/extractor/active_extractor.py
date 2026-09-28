from pathlib import Path
from io import BytesIO

import pandas as pd
import pyodbc
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[2]
QUERY_PATH = BASE_DIR / "queries" / "active_accounts.sql"


CLIENT_CONFIG = {
    "SBC AUTO LOAN": {
        "dsn": "cms_rs2",
        "reference": "SBC AL B6",
    },
    "SBC AUTO LOAN CURING": {
        "dsn": "cms_rs2",
        "reference": "SBC AL B2",
    },
    "SBC AUTO LOAN RECOV": {
        "dsn": "cms_rs2",
        "reference": "SBC AL Recovery",
    },
    "SBC CARDS CURING B2": {
        "dsn": "cms_rs",
        "reference": "SBC B2",
    },
    "SBC CURING B4": {
        "dsn": "cms_rs",
        "reference": "SBC B4",
    },
    "SBC CARDS CARDS & LOAN L6": {
        "dsn": "cms_rs",
        "reference": "SBC Recovery",
    },
    "SBC CARDS RECOV L1": {
        "dsn": "cms_rs",
        "reference": "SBC Recovery",
    },
    "SBC PL RECOV L1": {
        "dsn": "cms_rs",
        "reference": "SBC Recovery",
    },
    "SBC HOMELOAN": {
        "dsn": "cms_rs",
        "reference": "SBC Homeloan",
    },
    "SBC GEOX": {
        "dsn": "cms_rs",
        "reference": "SBC Geox",
    },
    "SBC Insurance": {
        "dsn": "cms_rs4",
        "reference": "SBC Insurance",
    },
    "SBC WBS": {
        "dsn": "cms_rs",
        "reference": "SBC WBS",
    },
    "SBF PL": {
        "dsn": "cms_rs",
        "reference": "SBF PL",
    },
    "SBF SALAD": {
        "dsn": "cms_rs",
        "reference": "SBF SALAD",
    },
}


@st.cache_resource
def get_connection(dsn):
    return pyodbc.connect(f"DSN={dsn};")


@st.cache_data(show_spinner=False)
def load_active_accounts(query_path, client_name, dsn):
    with open(query_path, "r", encoding="utf-8") as file:
        query = file.read()

    connection = get_connection(dsn)

    try:
        df = pd.read_sql_query(
            query,
            connection,
            params=(client_name,),
        )
    finally:
        connection.close()

    return df


def convert_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="Active Accounts",
        )

    output.seek(0)
    return output


def renderactiveextractor():
    st.title("Active Accounts Extractor")
    st.caption(
        "Extract all active accounts based on the selected client."
    )

    st.divider()

    # ============================================================
    # CLIENT SELECTION
    # ============================================================

    selected_client = st.selectbox(
        "Client Name",
        options=list(CLIENT_CONFIG.keys()),
        key="active_client",
    )

    client_config = CLIENT_CONFIG[selected_client]
    dsn = client_config["dsn"]

    st.caption(
        f"Database: {dsn}  |  Reference: {client_config['reference']}"
    )

    st.divider()

    # ============================================================
    # LOAD DATA
    # ============================================================

    if st.button(
        "Load Active Accounts",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.active_accounts_loaded = False

        try:
            with st.spinner(
                f"Loading active accounts for {selected_client}..."
            ):
                df = load_active_accounts(
                    str(QUERY_PATH),
                    selected_client,
                    dsn,
                )

            st.session_state.active_accounts_df = df
            st.session_state.active_accounts_client = selected_client
            st.session_state.active_accounts_loaded = True

        except Exception as e:
            st.error(f"Unable to load active accounts: {e}")
            return

    # ============================================================
    # DISPLAY RESULTS
    # ============================================================

    if not st.session_state.get("active_accounts_loaded", False):
        st.info("Select a client and click 'Load Active Accounts'.")
        return

    df = st.session_state.get(
        "active_accounts_df",
        pd.DataFrame(),
    )

    if df.empty:
        st.warning(
            f"No active accounts found for {selected_client}."
        )
        return

    st.success(
        f"{len(df):,} active accounts found for {selected_client}."
    )

    # ============================================================
    # METRICS
    # ============================================================

    total_accounts = len(df)

    if "Balance" in df.columns:
        balance_series = pd.to_numeric(
            df["Balance"],
            errors="coerce",
        ).fillna(0)

        total_balance = balance_series.sum()
        average_balance = (
            balance_series.mean()
            if len(balance_series)
            else 0
        )
    else:
        total_balance = 0
        average_balance = 0

    product_count = (
        df["Product"].nunique()
        if "Product" in df.columns
        else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Active Accounts",
            f"{total_accounts:,}",
        )

    with col2:
        st.metric(
            "Total Balance",
            f"₱{total_balance:,.2f}",
        )

    with col3:
        st.metric(
            "Average Balance",
            f"₱{average_balance:,.2f}",
        )

    with col4:
        st.metric(
            "Products",
            f"{product_count:,}",
        )

    st.divider()

    # ============================================================
    # PRODUCT SUMMARY
    # ============================================================

    if "Product" in df.columns:
        st.subheader("Product Summary")

        product_summary = (
            df.groupby("Product", dropna=False)
            .agg(
                Accounts=("Account No", "count"),
                Balance=("Balance", "sum"),
            )
            .reset_index()
        )

        product_summary["Balance"] = pd.to_numeric(
            product_summary["Balance"],
            errors="coerce",
        ).fillna(0)

        product_summary = product_summary.sort_values(
            "Accounts",
            ascending=False,
        )

        st.dataframe(
            product_summary,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # ============================================================
    # ACCOUNT DATA
    # ============================================================

    st.subheader("Active Account List")

    search = st.text_input(
        "Search Account / Card / Debtor",
        key="active_account_search",
    )

    display_df = df

    if search:
        search_value = search.strip().lower()

        searchable_columns = [
            column
            for column in [
                "Account No",
                "Card No",
                "Debtor",
                "Old IC",
            ]
            if column in display_df.columns
        ]

        if searchable_columns:
            mask = pd.Series(
                False,
                index=display_df.index,
            )

            for column in searchable_columns:
                mask = mask | (
                    display_df[column]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search_value,
                        regex=False,
                    )
                )

            display_df = display_df.loc[mask]

    st.caption(
        f"Showing {len(display_df):,} of {len(df):,} accounts"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # ============================================================
    # DOWNLOAD
    # ============================================================

    st.divider()

    st.subheader("Export")

    excel_file = convert_to_excel(df)

    st.download_button(
        label="Download Excel",
        data=excel_file,
        file_name=(
            f"{selected_client} - Active Accounts.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True,
    )

    csv_data = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=(
            f"{selected_client} - Active Accounts.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )