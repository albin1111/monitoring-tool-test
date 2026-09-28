import streamlit as st
import pyodbc
import pandas as pd
import time

from io import BytesIO
from datetime import date, timedelta
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
REFERENCE_DIRECTORY = BASE_DIR / "reference"


# ============================================================
# CLIENT CONFIGURATION
# ============================================================

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


# ============================================================
# DATABASE CONNECTION
# ============================================================

@st.cache_resource
def get_connection(dsn):
    return pyodbc.connect(f"DSN={dsn};")


# ============================================================
# LOAD SQL DATA
# ============================================================

@st.cache_data
def load_data(path: str, params: tuple = (), dsn: str = ""):
    start = time.time()

    conn = get_connection(dsn)

    with open(path, "r", encoding="utf-8") as file:
        query = file.read()

    df = pd.read_sql(
        query,
        conn,
        params=params,
    )

    duration = round(time.time() - start, 2)

    st.write(f"⏱ {path} loaded in {duration} sec")

    return df


# ============================================================
# LOAD REFERENCE
# ============================================================

@st.cache_data
def load_reference(reference_folder: str) -> pd.DataFrame:
    reference_path = (
        REFERENCE_DIRECTORY
        / reference_folder
        / "Reference.xlsx"
    )

    if not reference_path.exists():
        raise FileNotFoundError(
            f"Reference file not found:\n{reference_path}"
        )

    reference_df = pd.read_excel(reference_path)

    if reference_df.shape[1] < 2:
        raise ValueError(
            "Reference.xlsx must contain at least "
            "two columns: Status and Touchpoint."
        )

    reference_df = reference_df.iloc[:, :2].copy()

    reference_df.columns = [
        "Status",
        "Touchpoint",
    ]

    reference_df["Status"] = (
        reference_df["Status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    reference_df["Touchpoint"] = (
        reference_df["Touchpoint"]
        .astype(str)
        .str.strip()
    )

    reference_df = reference_df[
        reference_df["Status"].notna()
        & (reference_df["Status"] != "")
        & (reference_df["Status"] != "NAN")
    ]

    reference_df = (
        reference_df
        .drop_duplicates(
            subset=["Status"],
            keep="first",
        )
    )

    return reference_df


# ============================================================
# ADD TOUCHPOINT
# ============================================================

def apply_touchpoint(
    df: pd.DataFrame,
    reference_df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        df["Touchpoint"] = ""
        return df

    df["_STATUS_MATCH"] = (
        df["Status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    reference_map = dict(
        zip(
            reference_df["Status"],
            reference_df["Touchpoint"],
        )
    )

    df["Touchpoint"] = (
        df["_STATUS_MATCH"]
        .map(reference_map)
        .fillna("UNMAPPED")
    )

    df.drop(
        columns=["_STATUS_MATCH"],
        inplace=True,
    )

    return df


# ============================================================
# ADD PTP / KEPT FLAGS
# ============================================================

def add_status_flags(df: pd.DataFrame) -> pd.DataFrame:
    status_series = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["Is PTP"] = status_series.str.contains(
        "PTP",
        na=False,
    )

    df["Is KEPT"] = status_series.str.contains(
        "KEPT",
        na=False,
    )

    return df


# ============================================================
# CREATE ACCOUNT SUMMARY
# ============================================================

def create_account_summary(df: pd.DataFrame) -> pd.DataFrame:
    account_df = df.copy()

    account_df["Account No"] = (
        account_df["Account No"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    account_df = account_df[
        account_df["Account No"] != ""
    ].copy()

    account_summary = (
        account_df
        .groupby(
            "Account No",
            dropna=False,
            as_index=False,
        )
        .agg(
            Debtor=("Debtor", "first"),
            PTP=("Is PTP", "any"),
            KEPT=("Is KEPT", "any"),
            PTP_Amount=("PTP Amount", "sum"),
            PTP_Date=("PTP Date", "first"),
            First_Remark_Date=("Remark Date", "min"),
            Last_Remark_Date=("Remark Date", "max"),
        )
    )

    account_summary["PTP"] = account_summary["PTP"].map({
        True: "YES",
        False: "NO",
    })

    account_summary["KEPT"] = account_summary["KEPT"].map({
        True: "YES",
        False: "NO",
    })

    account_summary["Result"] = "PTP ONLY"

    account_summary.loc[
        (account_summary["PTP"] == "YES")
        & (account_summary["KEPT"] == "YES"),
        "Result",
    ] = "PTP + KEPT"

    account_summary.loc[
        (account_summary["PTP"] == "NO")
        & (account_summary["KEPT"] == "YES"),
        "Result",
    ] = "KEPT ONLY"

    account_summary["PTP_Amount"] = pd.to_numeric(
        account_summary["PTP_Amount"],
        errors="coerce",
    ).fillna(0)

    return account_summary


# ============================================================
# PTP AND KEPT EXTRACTOR
# ============================================================

def renderptpkeptextractor():

    st.title("PTP and KEPT Extractor")

    # ========================================================
    # CLIENT NAME
    # ========================================================

    selected_client = st.selectbox(
        "Client Name",
        options=list(CLIENT_CONFIG.keys()),
        key="ptp_client",
    )

    # ========================================================
    # CLIENT CONFIG
    # ========================================================

    client_config = CLIENT_CONFIG[
        selected_client
    ]

    dsn = client_config["dsn"]
    reference_folder = client_config["reference"]

    # ========================================================
    # DATE RANGE
    # ========================================================

    default_start = (
        date.today()
        - timedelta(days=1)
    )

    date_range = st.date_input(
        "PTP Created Date Range",
        value=(
            default_start,
            date.today(),
        ),
        key="ptp_date_range",
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    if len(date_range) != 2:
        st.info(
            "Please select both a start "
            "and end date."
        )
        return

    start_date, end_date = date_range

    if start_date > end_date:
        st.error(
            "Start date cannot be later "
            "than the end date."
        )
        return

    # ========================================================
    # GENERATE REPORT
    # ========================================================

    if st.button(
        "Generate PTP and KEPT Accounts",
        type="primary",
        key="generate_ptp",
    ):

        # ====================================================
        # SQL PARAMETERS
        # ====================================================

        params = (
            selected_client,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        # ====================================================
        # LOAD SQL DATA
        # ====================================================

        with st.spinner(
            f"Loading {selected_client} PTP and KEPT data..."
        ):
            try:
                followup_df = load_data(
                    "queries/ptp_kept.sql",
                    params=params,
                    dsn=dsn,
                )

            except Exception as e:
                st.error(
                    "Unable to load PTP and KEPT data:\n"
                    f"{e}"
                )
                return

        # ====================================================
        # CHECK RESULT
        # ====================================================

        if followup_df.empty:
            st.warning(
                "No PTP or KEPT records were found "
                f"for {selected_client} between "
                f"{start_date} and {end_date}."
            )
            return

        # ====================================================
        # LOAD REFERENCE
        # ====================================================

        with st.spinner(
            f"Loading {reference_folder} reference..."
        ):
            try:
                reference_df = load_reference(
                    reference_folder
                )

            except Exception as e:
                st.error(
                    "Unable to load Reference.xlsx:\n"
                    f"{e}"
                )
                return

        # ====================================================
        # APPLY TOUCHPOINT
        # ====================================================

        followup_df = apply_touchpoint(
            followup_df,
            reference_df,
        )

        # ====================================================
        # ADD PTP / KEPT FLAGS
        # ====================================================

        followup_df = add_status_flags(
            followup_df
        )

        # ====================================================
        # DERIVE DATE AND TIME
        # ====================================================

        if "DISPO DATE" in followup_df.columns:

            followup_df["DISPO DATE"] = pd.to_datetime(
                followup_df["DISPO DATE"],
                errors="coerce",
            )

            followup_df["Date"] = (
                followup_df["DISPO DATE"]
                .dt.date
            )

            followup_df["Time"] = (
                followup_df["DISPO DATE"]
                .dt.strftime("%I:%M:%S %p")
                .str.lstrip("0")
            )

        # ====================================================
        # METRIC FLAGS
        # ====================================================

        ptp_mask = followup_df["Is PTP"]
        kept_mask = followup_df["Is KEPT"]

        ptp_records = int(
            ptp_mask.sum()
        )

        kept_records = int(
            kept_mask.sum()
        )

        ptp_accounts = (
            followup_df.loc[
                ptp_mask,
                "Account No",
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

        kept_accounts = (
            followup_df.loc[
                kept_mask,
                "Account No",
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

        ptp_amount = pd.to_numeric(
            followup_df.loc[
                ptp_mask,
                "PTP Amount",
            ],
            errors="coerce",
        ).sum()

        kept_amount = pd.to_numeric(
            followup_df.loc[
                kept_mask,
                "PTP Amount",
            ],
            errors="coerce",
        ).sum()

        average_ptp_amount = (
            ptp_amount / ptp_records
            if ptp_records > 0
            else 0
        )

        average_kept_amount = (
            kept_amount / kept_records
            if kept_records > 0
            else 0
        )

        kept_rate = (
            kept_records / ptp_records * 100
            if ptp_records > 0
            else 0
        )

        # ====================================================
        # ACCOUNT SUMMARY
        # ====================================================

        account_summary = create_account_summary(
            followup_df
        )

        both_accounts = int(
            (
                (account_summary["PTP"] == "YES")
                & (account_summary["KEPT"] == "YES")
            ).sum()
        )

        ptp_only_accounts = int(
            (
                (account_summary["PTP"] == "YES")
                & (account_summary["KEPT"] == "NO")
            ).sum()
        )

        kept_only_accounts = int(
            (
                (account_summary["PTP"] == "NO")
                & (account_summary["KEPT"] == "YES")
            ).sum()
        )

        account_kept_rate = (
            both_accounts / ptp_accounts * 100
            if ptp_accounts > 0
            else 0
        )

        # ====================================================
        # SUCCESS
        # ====================================================

        st.success(
            f"Data generated successfully! "
            f"{len(followup_df):,} records found."
        )

        # ====================================================
        # PTP METRICS
        # ====================================================

        st.subheader("PTP Metrics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "PTP Records",
                f"{ptp_records:,}",
            )

        with col2:
            st.metric(
                "PTP Unique Accounts",
                f"{ptp_accounts:,}",
            )

        with col3:
            st.metric(
                "Total PTP Amount",
                f"{ptp_amount:,.2f}",
            )

        with col4:
            st.metric(
                "Average PTP Amount",
                f"{average_ptp_amount:,.2f}",
            )

        # ====================================================
        # KEPT METRICS
        # ====================================================

        st.subheader("KEPT Metrics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "KEPT Records",
                f"{kept_records:,}",
            )

        with col2:
            st.metric(
                "KEPT Unique Accounts",
                f"{kept_accounts:,}",
            )

        with col3:
            st.metric(
                "KEPT Amount",
                f"{kept_amount:,.2f}",
            )

        with col4:
            st.metric(
                "KEPT Rate",
                f"{kept_rate:.2f}%",
            )

        # ====================================================
        # ACCOUNT METRICS
        # ====================================================

        st.subheader("Account Conversion")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "PTP Accounts",
                f"{ptp_accounts:,}",
            )

        with col2:
            st.metric(
                "PTP + KEPT",
                f"{both_accounts:,}",
            )

        with col3:
            st.metric(
                "PTP Only",
                f"{ptp_only_accounts:,}",
            )

        with col4:
            st.metric(
                "Account KEPT Rate",
                f"{account_kept_rate:.2f}%",
            )

        st.caption(
            "Account KEPT Rate = PTP accounts that also had "
            "a KEPT record ÷ PTP unique accounts."
        )

        # ====================================================
        # ACCOUNT STATUS SUMMARY
        # ====================================================

        st.subheader("Account Status Summary")

        status_summary = pd.DataFrame(
            {
                "Result": [
                    "PTP + KEPT",
                    "PTP ONLY",
                    "KEPT ONLY",
                ],
                "Accounts": [
                    both_accounts,
                    ptp_only_accounts,
                    kept_only_accounts,
                ],
            }
        )

        st.dataframe(
            status_summary,
            width="stretch",
            hide_index=True,
        )

        # ====================================================
        # ACCOUNT LIST
        # ====================================================

        st.subheader(
            "Account List"
        )

        display_account_summary = account_summary.copy()

        display_account_summary = (
            display_account_summary.rename(
                columns={
                    "PTP_Amount": "PTP Amount",
                    "PTP_Date": "PTP Date",
                    "First_Remark_Date": "First Remark Date",
                    "Last_Remark_Date": "Last Remark Date",
                }
            )
        )

        display_account_summary["PTP Amount"] = (
            pd.to_numeric(
                display_account_summary["PTP Amount"],
                errors="coerce",
            ).fillna(0)
        )

        st.dataframe(
            display_account_summary[
                [
                    "Account No",
                    "Debtor",
                    "PTP",
                    "KEPT",
                    "Result",
                    "PTP Amount",
                    "PTP Date",
                    "First Remark Date",
                    "Last Remark Date",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

        # ====================================================
        # TOUCHPOINT SUMMARY
        # ====================================================

        st.subheader(
            "Touchpoint Summary"
        )

        touchpoint_summary = (
            followup_df[
                "Touchpoint"
            ]
            .value_counts()
            .rename_axis(
                "Touchpoint"
            )
            .reset_index(
                name="Count"
            )
        )

        st.dataframe(
            touchpoint_summary,
            width="stretch",
            hide_index=True,
        )

        # ====================================================
        # RAW PTP / KEPT RESULT
        # ====================================================

        st.subheader(
            "PTP and KEPT Result"
        )

        st.dataframe(
            followup_df,
            width="stretch",
            hide_index=True,
        )

        # ====================================================
        # EXCEL EXPORT
        # ====================================================

        buf = BytesIO()

        with pd.ExcelWriter(
            buf,
            engine="openpyxl",
        ) as writer:

            followup_df.to_excel(
                writer,
                sheet_name="PTP KEPT Records",
                index=False,
            )

            display_account_summary.to_excel(
                writer,
                sheet_name="Account Summary",
                index=False,
            )

            status_summary.to_excel(
                writer,
                sheet_name="Status Summary",
                index=False,
            )

            touchpoint_summary.to_excel(
                writer,
                sheet_name="Touchpoint Summary",
                index=False,
            )

        buf.seek(0)

        # ====================================================
        # DOWNLOAD
        # ====================================================

        st.download_button(
            label="Download Excel",
            data=buf,
            file_name=(
                f"PTPKEPT_"
                f"{selected_client}_"
                f"{start_date}_to_"
                f"{end_date}.xlsx"
            ),
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )