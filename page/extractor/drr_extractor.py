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
    return pyodbc.connect(
        f"DSN={dsn};"
    )


# ============================================================
# LOAD SQL DATA
# ============================================================

@st.cache_data
def load_data(
    path: str,
    params: tuple = (),
    dsn: str = "",
):
    start = time.time()

    conn = get_connection(dsn)

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        query = file.read()

    df = pd.read_sql(
        query,
        conn,
        params=params,
    )

    duration = round(
        time.time() - start,
        2,
    )

    st.write(
        f"⏱ {path} loaded in {duration} sec"
    )

    return df


# ============================================================
# LOAD REFERENCE
# ============================================================

@st.cache_data
def load_reference(reference_folder):
    reference_file = (
        REFERENCE_DIRECTORY
        / reference_folder
        / "Reference.xlsx"
    )

    if not reference_file.exists():
        raise FileNotFoundError(
            f"Reference file not found:\n"
            f"{reference_file}"
        )

    reference_df = pd.read_excel(
        reference_file,
        sheet_name="REFERENCE",
    )

    required_columns = [
        "CMS STATUS",
        "TOUCHPOINT",
        "RIGHT PARTY CONTACT",
        "PTP",
        "KEPT",
        "REACH",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in reference_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing columns in Reference.xlsx: "
            + ", ".join(missing_columns)
        )

    reference_df["STATUS_KEY"] = (
        reference_df["CMS STATUS"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    reference_df = reference_df.drop_duplicates(
        subset=["STATUS_KEY"],
        keep="first",
    )

    return reference_df


# ============================================================
# APPLY REFERENCE MAPPING
# ============================================================

def apply_reference_mapping(
    df,
    reference_folder,
):
    reference_df = load_reference(
        reference_folder
    )

    if "Status" not in df.columns:
        raise ValueError(
            'The DRR query result does not contain '
            'a "Status" column.'
        )

    df["STATUS_KEY"] = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    reference_mapping = reference_df[
        [
            "STATUS_KEY",
            "TOUCHPOINT",
            "RIGHT PARTY CONTACT",
            "PTP",
            "KEPT",
            "REACH",
        ]
    ].copy()

    df = df.merge(
        reference_mapping,
        on="STATUS_KEY",
        how="left",
    )

    df = df.drop(
        columns=["STATUS_KEY"],
        errors="ignore",
    )

    return df


# ============================================================
# PREPARE METRIC COLUMNS
# ============================================================

def prepare_metric_columns(df):
    metric_columns = [
        "RIGHT PARTY CONTACT",
        "PTP",
        "KEPT",
        "REACH",
    ]

    for column in metric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0)

    return df


# ============================================================
# SAFE RATE
# ============================================================

def calculate_rate(
    numerator,
    denominator,
):
    if denominator == 0:
        return 0

    return (
        numerator
        / denominator
        * 100
    )


# ============================================================
# OVERALL METRICS
# ============================================================

def calculate_metrics(df):
    total_records = len(df)

    reach_count = int(
        df["REACH"].sum()
    )

    rpc_count = int(
        df["RIGHT PARTY CONTACT"].sum()
    )

    ptp_count = int(
        df["PTP"].sum()
    )

    kept_count = int(
        df["KEPT"].sum()
    )

    return {
        "total_records": total_records,
        "reach": reach_count,
        "rpc": rpc_count,
        "ptp": ptp_count,
        "kept": kept_count,
        "reach_rate": calculate_rate(
            reach_count,
            total_records,
        ),
        "rpc_rate": calculate_rate(
            rpc_count,
            reach_count,
        ),
        "ptp_rate": calculate_rate(
            ptp_count,
            rpc_count,
        ),
        "kept_rate": calculate_rate(
            kept_count,
            ptp_count,
        ),
    }


# ============================================================
# TOUCHPOINT METRICS
# ============================================================

def calculate_touchpoint_metrics(df):
    working_df = df.copy()

    working_df["TOUCHPOINT"] = (
        working_df["TOUCHPOINT"]
        .fillna("UNMAPPED")
        .astype(str)
        .str.strip()
    )

    working_df.loc[
        working_df["TOUCHPOINT"] == "",
        "TOUCHPOINT",
    ] = "UNMAPPED"

    touchpoint_df = (
        working_df
        .groupby(
            "TOUCHPOINT",
            as_index=False,
        )
        .agg(
            RECORDS=(
                "TOUCHPOINT",
                "size",
            ),
            REACH=(
                "REACH",
                "sum",
            ),
            RIGHT_PARTY_CONTACT=(
                "RIGHT PARTY CONTACT",
                "sum",
            ),
            PTP=(
                "PTP",
                "sum",
            ),
            KEPT=(
                "KEPT",
                "sum",
            ),
        )
    )

    integer_columns = [
        "RECORDS",
        "REACH",
        "RIGHT_PARTY_CONTACT",
        "PTP",
        "KEPT",
    ]

    for column in integer_columns:
        touchpoint_df[column] = (
            touchpoint_df[column]
            .astype(int)
        )

    touchpoint_df["REACH_RATE"] = (
        touchpoint_df.apply(
            lambda row: calculate_rate(
                row["REACH"],
                row["RECORDS"],
            ),
            axis=1,
        )
    )

    touchpoint_df["RPC_RATE"] = (
        touchpoint_df.apply(
            lambda row: calculate_rate(
                row["RIGHT_PARTY_CONTACT"],
                row["REACH"],
            ),
            axis=1,
        )
    )

    touchpoint_df["PTP_RATE"] = (
        touchpoint_df.apply(
            lambda row: calculate_rate(
                row["PTP"],
                row["RIGHT_PARTY_CONTACT"],
            ),
            axis=1,
        )
    )

    touchpoint_df["KEPT_RATE"] = (
        touchpoint_df.apply(
            lambda row: calculate_rate(
                row["KEPT"],
                row["PTP"],
            ),
            axis=1,
        )
    )

    rate_columns = [
        "REACH_RATE",
        "RPC_RATE",
        "PTP_RATE",
        "KEPT_RATE",
    ]

    touchpoint_df[rate_columns] = (
        touchpoint_df[rate_columns]
        .round(2)
    )

    return touchpoint_df


# ============================================================
# ACCOUNT × TOUCHPOINT
# ============================================================

def calculate_account_touchpoint_metrics(df):
    if "Account No" not in df.columns:
        raise ValueError(
            'The DRR query result does not contain '
            '"Account No". '
            f"Available columns: "
            f"{', '.join(df.columns)}"
        )

    if "TOUCHPOINT" not in df.columns:
        raise ValueError(
            'The data does not contain '
            '"TOUCHPOINT".'
        )

    working_df = df[
        [
            "Account No",
            "TOUCHPOINT",
        ]
    ].copy()

    working_df["Account No"] = (
        working_df["Account No"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    working_df["TOUCHPOINT"] = (
        working_df["TOUCHPOINT"]
        .fillna("UNMAPPED")
        .astype(str)
        .str.strip()
    )

    working_df.loc[
        working_df["TOUCHPOINT"] == "",
        "TOUCHPOINT",
    ] = "UNMAPPED"

    working_df = working_df[
        (working_df["Account No"] != "")
        & (
            working_df["Account No"].str.upper()
            != "NAN"
        )
    ]

    if working_df.empty:
        return pd.DataFrame(
            columns=["Account No"]
        )

    # IMPORTANT:
    # Every returned record is counted.
    # Duplicate Account No + TOUCHPOINT
    # records are intentionally included.

    account_touchpoint_df = (
        working_df
        .groupby(
            [
                "Account No",
                "TOUCHPOINT",
            ]
        )
        .size()
        .reset_index(
            name="COUNT"
        )
    )

    account_touchpoint_df = (
        account_touchpoint_df
        .pivot(
            index="Account No",
            columns="TOUCHPOINT",
            values="COUNT",
        )
        .fillna(0)
        .reset_index()
    )

    account_touchpoint_df.columns.name = None

    for column in account_touchpoint_df.columns:
        if column != "Account No":
            account_touchpoint_df[column] = (
                account_touchpoint_df[column]
                .astype(int)
            )

    preferred_order = [
        "Account No",
        "CALL",
        "EMAIL",
        "FIELD",
        "SMS",
        "UNMAPPED",
        "VIBER",
    ]

    existing_columns = [
        column
        for column in preferred_order
        if column in account_touchpoint_df.columns
    ]

    other_columns = [
        column
        for column in account_touchpoint_df.columns
        if column not in existing_columns
    ]

    account_touchpoint_df = (
        account_touchpoint_df[
            existing_columns
            + sorted(other_columns)
        ]
    )

    return account_touchpoint_df


# ============================================================
# DISPLAY OVERALL METRICS
# ============================================================

def display_overall_metrics(df):
    metrics = calculate_metrics(df)

    st.subheader("DRR Metrics")

    columns = st.columns(5)

    with columns[0]:
        st.metric(
            "RECORDS",
            f"{metrics['total_records']:,}",
            border=True,
        )

    with columns[1]:
        st.metric(
            "REACH",
            f"{metrics['reach']:,}",
            f"{metrics['reach_rate']:.2f}%",
            border=True,
        )

    with columns[2]:
        st.metric(
            "RIGHT PARTY CONTACT",
            f"{metrics['rpc']:,}",
            f"{metrics['rpc_rate']:.2f}%",
            border=True,
        )

    with columns[3]:
        st.metric(
            "PTP",
            f"{metrics['ptp']:,}",
            f"{metrics['ptp_rate']:.2f}%",
            border=True,
        )

    with columns[4]:
        st.metric(
            "KEPT",
            f"{metrics['kept']:,}",
            f"{metrics['kept_rate']:.2f}%",
            border=True,
        )

    st.caption(
        "Reach Rate = Reach ÷ Records | "
        "RPC Rate = RPC ÷ Reach | "
        "PTP Rate = PTP ÷ RPC | "
        "Kept Rate = Kept ÷ PTP"
    )


# ============================================================
# DISPLAY TOUCHPOINT METRICS
# ============================================================

def display_touchpoint_metrics(df):
    touchpoint_df = (
        calculate_touchpoint_metrics(df)
    )

    if touchpoint_df.empty:
        return

    st.subheader(
        "Touchpoint Performance"
    )

    for start in range(
        0,
        len(touchpoint_df),
        4,
    ):
        row = touchpoint_df.iloc[
            start:start + 4
        ]

        columns = st.columns(
            len(row)
        )

        for column, (_, data) in zip(
            columns,
            row.iterrows(),
        ):
            with column:
                st.metric(
                    data["TOUCHPOINT"],
                    f"{data['RECORDS']:,}",
                    f"{data['REACH_RATE']:.2f}% Reach",
                    border=True,
                )

    display_df = touchpoint_df.rename(
        columns={
            "RIGHT_PARTY_CONTACT":
                "RIGHT PARTY CONTACT",
            "REACH_RATE":
                "REACH %",
            "RPC_RATE":
                "RPC %",
            "PTP_RATE":
                "PTP %",
            "KEPT_RATE":
                "KEPT %",
        }
    )

    display_df = display_df[
        [
            "TOUCHPOINT",
            "RECORDS",
            "REACH",
            "RIGHT PARTY CONTACT",
            "PTP",
            "KEPT",
            "REACH %",
            "RPC %",
            "PTP %",
            "KEPT %",
        ]
    ]

    st.dataframe(
        display_df,
        hide_index=True,
        width="stretch",
    )


# ============================================================
# DISPLAY ACCOUNT × TOUCHPOINT
# ============================================================

def display_account_touchpoint_metrics(df):
    metrics_df = (
        calculate_account_touchpoint_metrics(df)
    )

    st.subheader(
        "Account Touchpoint Summary"
    )

    if metrics_df.empty:
        st.info(
            'No valid "Account No" records '
            "were returned."
        )
        return

    st.dataframe(
        metrics_df,
        hide_index=True,
        width="stretch",
    )

    st.caption(
        "Each touchpoint column shows the number "
        "of returned DRR records for that account. "
        "Duplicate records are included."
    )


# ============================================================
# DRR EXTRACTOR
# ============================================================

def renderdrrextractor():

    st.title(
        "Daily Remark Report (DRR) Extractor"
    )

    # ========================================================
    # CLIENT NAME
    # ========================================================

    selected_client = st.selectbox(
        "Client Name",
        options=list(
            CLIENT_CONFIG.keys()
        ),
        key="drr_client",
    )

    # ========================================================
    # DYNAMIC CLIENT CONFIG
    # ========================================================

    client_config = CLIENT_CONFIG[
        selected_client
    ]

    dsn = client_config["dsn"]

    reference_folder = (
        client_config["reference"]
    )

    # ========================================================
    # DATE RANGE
    # ========================================================

    default_start = (
        date.today()
        - timedelta(days=1)
    )

    date_range = st.date_input(
        "Followup Date Range",
        value=(
            default_start,
            date.today(),
        ),
        key="drr_date_range",
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

    # ========================================================
    # GENERATE REPORT
    # ========================================================

    if st.button(
        "Generate Daily Remark Report",
        type="primary",
        key="generate_drr",
    ):

        # ====================================================
        # LOAD SQL DATA
        # ====================================================

        with st.spinner(
            f"Loading {selected_client} data..."
        ):

            params = (
                selected_client,
                start_date.strftime(
                    "%Y-%m-%d"
                ),
                end_date.strftime(
                    "%Y-%m-%d"
                ),
            )

            try:
                followup_df = load_data(
                    "queries/drr.sql",
                    params=params,
                    dsn=dsn,
                )

            except Exception as e:
                st.error(
                    "Unable to load DRR data:\n"
                    f"{e}"
                )
                return

        # ====================================================
        # APPLY REFERENCE MAPPING
        # ====================================================

        with st.spinner(
            "Loading reference mapping..."
        ):

            try:
                followup_df = (
                    apply_reference_mapping(
                        followup_df,
                        reference_folder,
                    )
                )

            except Exception as e:
                st.error(
                    "Unable to load reference "
                    f"for {selected_client}:\n"
                    f"{e}"
                )
                return

        # ====================================================
        # PREPARE METRICS
        # ====================================================

        followup_df = (
            prepare_metric_columns(
                followup_df
            )
        )

        # ====================================================
        # DERIVE DATE AND TIME
        # ====================================================

        if "DISPO DATE" in followup_df.columns:

            followup_df["DISPO DATE"] = (
                pd.to_datetime(
                    followup_df["DISPO DATE"],
                    errors="coerce",
                )
            )

            followup_df["Date"] = (
                followup_df["DISPO DATE"]
                .dt.date
            )

            followup_df["Time"] = (
                followup_df["DISPO DATE"]
                .dt.strftime(
                    "%I:%M:%S %p"
                )
                .str.lstrip("0")
            )

        # ====================================================
        # SUCCESS
        # ====================================================

        st.success(
            "DRR data generated successfully!"
        )

        # ====================================================
        # OVERALL METRICS
        # ====================================================

        display_overall_metrics(
            followup_df
        )

        # ====================================================
        # TOUCHPOINT PERFORMANCE
        # ====================================================

        display_touchpoint_metrics(
            followup_df
        )

        # ====================================================
        # ACCOUNT × TOUCHPOINT
        # ====================================================

        try:
            display_account_touchpoint_metrics(
                followup_df
            )

        except Exception as e:
            st.error(
                "Unable to generate Account "
                "Touchpoint Summary:\n"
                f"{e}"
            )

        # ====================================================
        # DRR RESULT
        # ====================================================

        st.subheader(
            "DRR Result"
        )

        st.dataframe(
            followup_df,
            width="stretch",
        )

        # ====================================================
        # EXCEL EXPORT
        # ====================================================

        buf = BytesIO()

        followup_df.to_excel(
            buf,
            index=False,
        )

        buf.seek(0)

        # ====================================================
        # DOWNLOAD
        # ====================================================

        st.download_button(
            label="Download DRR",
            data=buf,
            file_name=(
                f"DRR_"
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