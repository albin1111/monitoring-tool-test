from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
import polars as pl
import streamlit as st
from src.config import (
    CAMPAIGNS,
    MONTHS,
    FILE_TYPES,
    get_upload_directory,
    get_processed_directory,
)

from src.database import get_connection

from src.ingest import (
    read_tabular_file,
    normalize_columns,
)


# ============================================================
# OPTIONS
# ============================================================

CAMPAIGN_OPTIONS = list(CAMPAIGNS.values())
MONTH_OPTIONS = list(MONTHS.values())
FILE_TYPE_OPTIONS = list(FILE_TYPES.values())


# ============================================================
# CALLBACKS
# ============================================================

def update_campaign():
    st.session_state.selected_campaign = (
        st.session_state.upload_campaign_widget
    )


def update_month():
    st.session_state.selected_month = (
        st.session_state.upload_month_widget
    )


def update_file_type():
    st.session_state.selected_file_type = (
        st.session_state.upload_file_type_widget
    )


# ============================================================
# READ FILE
# ============================================================

def read_uploaded_file(
    file_path,
    password=None,
):
    """Read the uploaded file and pass the entered password to ingest.py."""
    return read_tabular_file(
        path=file_path,
        password=password,
    )


# ============================================================
# MAIN PAGE
# ============================================================

def renderupload():

    st.title("Upload Data")

    # ========================================================
    # RESTORE WIDGET STATE
    # ========================================================

    if "upload_campaign_widget" not in st.session_state:
        st.session_state.upload_campaign_widget = (
            st.session_state.selected_campaign
        )

    if "upload_month_widget" not in st.session_state:
        st.session_state.upload_month_widget = (
            st.session_state.selected_month
        )

    if "upload_file_type_widget" not in st.session_state:
        st.session_state.upload_file_type_widget = (
            st.session_state.selected_file_type
        )

    # ========================================================
    # SELECTORS
    # ========================================================

    col1, col2, col3 = st.columns(
        [1.2, 1, 1]
    )

    with col1:

        st.selectbox(
            "Campaign",
            CAMPAIGN_OPTIONS,
            index=None,
            placeholder="Select a campaign...",
            key="upload_campaign_widget",
            on_change=update_campaign,
        )

    with col2:

        st.selectbox(
            "Month",
            MONTH_OPTIONS,
            index=None,
            placeholder="Select a month...",
            key="upload_month_widget",
            on_change=update_month,
        )

    with col3:

        st.selectbox(
            "File Type",
            FILE_TYPE_OPTIONS,
            index=None,
            placeholder="Select a file type...",
            key="upload_file_type_widget",
            on_change=update_file_type,
        )

    # ========================================================
    # GET PERSISTENT VALUES
    # ========================================================

    campaign = st.session_state.selected_campaign
    month = st.session_state.selected_month
    file_type = st.session_state.selected_file_type

    # ========================================================
    # VALIDATION
    # ========================================================

    if (
        campaign is None
        or month is None
        or file_type is None
    ):

        st.info(
            "Please select a campaign, month, and file type."
        )

        return

    # ========================================================
    # DIRECTORIES
    # ========================================================

    upload_directory = get_upload_directory(
        campaign,
        month,
        file_type,
    )

    processed_directory = get_processed_directory(
        campaign,
        month,
        file_type,
    )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    processed_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    st.success(
        f"Campaign: **{campaign}** | "
        f"Month: **{month}** | "
        f"File Type: **{file_type}**"
    )

    st.caption(
        f"Upload path: `{upload_directory}`"
    )

    st.caption(
        f"Processed path: `{processed_directory}`"
    )

    # ============================================================
    # EXCEL PASSWORD
    # ============================================================

    password = st.text_input(
        "Excel Password",
        type="password",
        placeholder="Enter password if Excel files are protected...",
        help=(
            "The same password will be used for all "
            "password-protected Excel files."
        ),
        key="upload_file_password",
    )

    st.caption(
        "Leave blank if the uploaded Excel files are not "
        "password protected."
    )

    # ========================================================
    # FILE UPLOADER
    # ========================================================

    uploaded_files = st.file_uploader(
        "Select CSV, Excel (including XLSB), or Parquet files",
        type=[
            "csv",
            "xlsx",
            "xls",
            "xlsm",
            "xlsb",
            "parquet",
        ],
        accept_multiple_files=True,
        key="upload_files",
    )

    if not uploaded_files:
        return

    st.write(
        f"**{len(uploaded_files):,} file(s) selected**"
    )

    process_files = st.button(
        "Process Files",
        type="primary",
        key="process_uploaded_files",
    )

    if not process_files:
        return

    # Read the current widget value at click time.
    password = st.session_state.get(
        "upload_file_password",
        "",
    )

    # ========================================================
    # PROCESS FILES
    # ========================================================

    for uploaded_file in uploaded_files:

        import_id = str(uuid4())

        extension = Path(
            uploaded_file.name
        ).suffix.lower()

        stored_path = (
            upload_directory
            / f"{import_id}{extension}"
        )

        # Use the original uploaded file name for the processed Parquet.
        source_stem = Path(
            uploaded_file.name
        ).stem

        safe_stem = (
            source_stem
            .replace("/", "_")
            .replace("\\", "_")
            .strip()
        )

        if not safe_stem:
            safe_stem = "file"

        processed_path = (
            processed_directory
            / f"{safe_stem}_{import_id[:8]}.parquet"
        )

        # Guard against overwriting a previous upload with the same name.
        if processed_path.exists():
            processed_path = (
                processed_directory
                / f"{safe_stem}_{import_id}.parquet"
            )

        try:

            # ----------------------------------------------
            # STORE ORIGINAL FILE
            # ----------------------------------------------

            stored_path.write_bytes(
                uploaded_file.getvalue()
            )

            # ----------------------------------------------
            # READ FILE
            # ----------------------------------------------

            frame = read_uploaded_file(
                stored_path,
                password=password,
            )

            # ----------------------------------------------
            # NORMALIZE
            # ----------------------------------------------

            frame = normalize_columns(
                frame
            )

            # ----------------------------------------------
            # ADD METADATA
            # ----------------------------------------------

            frame = frame.with_columns(
                pl.lit(import_id).alias(
                    "import_id"
                ),
                pl.lit(
                    uploaded_file.name
                ).alias(
                    "source_file"
                ),
                pl.lit(campaign).alias(
                    "campaign"
                ),
                pl.lit(month).alias(
                    "month"
                ),
                pl.lit(file_type).alias(
                    "file_type"
                ),
            )

            # ----------------------------------------------
            # STORE PROCESSED PARQUET
            # ----------------------------------------------

            frame.write_parquet(
                processed_path,
                compression="zstd",
            )

            # ----------------------------------------------
            # DATABASE
            # ----------------------------------------------

            connection = get_connection()

            try:

                connection.execute(
                    """
                    INSERT INTO imports (
                        import_id,
                        original_name,
                        stored_path,
                        imported_at,
                        row_count,
                        column_count,
                        campaign,
                        month,
                        file_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        import_id,
                        uploaded_file.name,
                        str(stored_path),
                        datetime.now(timezone.utc),
                        frame.height,
                        frame.width,
                        campaign,
                        month,
                        file_type,
                    ],
                )

            finally:

                connection.close()

            # ----------------------------------------------
            # SUCCESS
            # ----------------------------------------------

            st.success(
                f"{uploaded_file.name}: "
                f"{frame.height:,} rows imported."
            )

            st.caption(
                f"Processed file: `{processed_path}`"
            )

            st.dataframe(
                frame.head(20),
                width="stretch",
            )

            del frame

        except Exception as error:

            st.error(
                f"{uploaded_file.name}: {error}"
            )

            if stored_path.exists():
                stored_path.unlink()

            if processed_path.exists():
                processed_path.unlink()