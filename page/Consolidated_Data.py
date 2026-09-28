from pathlib import Path
from datetime import datetime
import io
import zipfile
import tempfile

import polars as pl
import streamlit as st

from src.config import (
    CAMPAIGNS,
    MONTHS,
    FILE_TYPES,
    PROCESSED_DIRECTORY,
    CONSOLIDATED_DIRECTORY,
)


# ============================================================
# OPTIONS
# ============================================================

CAMPAIGN_OPTIONS = list(CAMPAIGNS.values())
MONTH_OPTIONS = list(MONTHS.values())
FILE_TYPE_OPTIONS = list(FILE_TYPES.values())


# ============================================================
# MONTH FOLDERS
# ============================================================

MONTH_FOLDERS = {
    "January": "01_January",
    "February": "02_February",
    "March": "03_March",
    "April": "04_April",
    "May": "05_May",
    "June": "06_June",
    "July": "07_July",
    "August": "08_August",
    "September": "09_September",
    "October": "10_October",
    "November": "11_November",
    "December": "12_December",
}


# ============================================================
# CALLBACKS
# ============================================================

def update_campaign():
    st.session_state.selected_campaign = (
        st.session_state.conso_campaign_widget
    )


def update_month():
    st.session_state.selected_month = (
        st.session_state.conso_month_widget
    )


def update_file_type():
    st.session_state.selected_file_type = (
        st.session_state.conso_file_type_widget
    )


# ============================================================
# PATH HELPERS
# ============================================================

def safe_campaign_name(value):
    return (
        str(value)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def safe_file_type_name(value):
    return (
        str(value)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
    )


def get_month_folder(month):
    if month not in MONTH_FOLDERS:
        raise ValueError(
            f"Invalid month selected: {month}"
        )

    return MONTH_FOLDERS[month]


def get_processed_path(
    campaign,
    month,
    file_type,
):
    return (
        PROCESSED_DIRECTORY
        / safe_campaign_name(campaign)
        / get_month_folder(month)
        / safe_file_type_name(file_type)
    )


def get_consolidated_path(
    campaign,
    month,
    file_type,
):
    directory = (
        CONSOLIDATED_DIRECTORY
        / safe_campaign_name(campaign)
        / get_month_folder(month)
        / safe_file_type_name(file_type)
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# ============================================================
# FILE DISCOVERY
# ============================================================

def get_supported_files(directory):
    if not directory.exists():
        return []

    supported_extensions = {
        ".parquet",
        ".csv",
        ".xlsx",
        ".xls",
    }

    return [
        path
        for path in sorted(directory.iterdir())
        if (
            path.is_file()
            and path.suffix.lower()
            in supported_extensions
        )
    ]


# ============================================================
# READ FILE
# ============================================================

def read_file(path):
    extension = path.suffix.lower()

    if extension == ".parquet":
        return pl.read_parquet(path)

    if extension == ".csv":
        return pl.read_csv(
            path,
            infer_schema_length=0,
            ignore_errors=True,
        )

    if extension in {
        ".xlsx",
        ".xls",
        ".xlsm",
    }:
        return pl.read_excel(
            path,
            infer_schema_length=0,
        )

    raise ValueError(
        f"Unsupported file type: {extension}"
    )


# ============================================================
# NORMALIZE NESTED COLUMNS
# ============================================================

def normalize_nested_columns(df):
    expressions = []

    for column_name, dtype in zip(
        df.columns,
        df.dtypes,
    ):
        if isinstance(dtype, pl.List):
            expressions.append(
                pl.col(column_name)
                .cast(pl.String)
                .alias(column_name)
            )

        elif isinstance(dtype, pl.Struct):
            expressions.append(
                pl.col(column_name)
                .cast(pl.String)
                .alias(column_name)
            )

    if expressions:
        df = df.with_columns(
            expressions
        )

    return df


# ============================================================
# ROW COUNT
# ============================================================

def get_row_count(path):
    try:
        if path.suffix.lower() == ".parquet":
            return (
                pl.scan_parquet(path)
                .select(pl.len())
                .collect()
                .item()
            )

        if path.suffix.lower() == ".csv":
            return (
                pl.scan_csv(
                    path,
                    infer_schema_length=0,
                    ignore_errors=True,
                )
                .select(pl.len())
                .collect()
                .item()
            )

        return read_file(path).height

    except Exception:
        return 0


# ============================================================
# ZIP
# ============================================================

def create_zip(files):
    output = io.BytesIO()

    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:

        for filename, data in files:
            archive.writestr(
                filename,
                data,
            )

    output.seek(0)

    return output.getvalue()


# ============================================================
# FILE NAME
# ============================================================

def get_consolidated_filename(
    month,
    file_type,
    extension,
):
    """
    Creates the consolidated filename using:

    [MONTH] [YEAR] Consolidated [FILE TYPE].[EXT]

    Example:
    August 2026 Consolidated CC DAR.csv
    """

    year = datetime.now().year

    # Keep the selected month as displayed in the UI.
    month_name = str(month).strip()

    # Keep spaces in the file type so the filename is readable.
    # Only remove characters that are invalid in Windows filenames.
    file_type_name = (
        str(file_type)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )

    return (
        f"{month_name} {year} "
        f"Consolidated {file_type_name}"
        f".{extension}"
    )


# ============================================================
# MAIN PAGE
# ============================================================

def renderconso():

    st.title("Consolidator")

    st.caption(
        "Select the campaign, month, and file type "
        "to consolidate processed files."
    )

    # ========================================================
    # RESTORE CONSOLIDATOR WIDGET STATE
    # ========================================================

    if "conso_campaign_widget" not in st.session_state:
        st.session_state.conso_campaign_widget = (
            st.session_state.selected_campaign
        )

    if "conso_month_widget" not in st.session_state:
        st.session_state.conso_month_widget = (
            st.session_state.selected_month
        )

    if "conso_file_type_widget" not in st.session_state:
        st.session_state.conso_file_type_widget = (
            st.session_state.selected_file_type
        )

    # ========================================================
    # SELECTORS
    # ========================================================

    col1, col2, col3 = st.columns(3)

    with col1:
        st.selectbox(
            "Campaign",
            CAMPAIGN_OPTIONS,
            index=None,
            placeholder="Select a campaign...",
            key="conso_campaign_widget",
            on_change=update_campaign,
        )

    with col2:
        st.selectbox(
            "Month",
            MONTH_OPTIONS,
            index=None,
            placeholder="Select a month...",
            key="conso_month_widget",
            on_change=update_month,
        )

    with col3:
        st.selectbox(
            "File Type",
            FILE_TYPE_OPTIONS,
            index=None,
            placeholder="Select a file type...",
            key="conso_file_type_widget",
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
            "Select a campaign, month, and file type "
            "to continue."
        )
        return

    # ========================================================
    # PATHS
    # ========================================================

    processed_directory = get_processed_path(
        campaign,
        month,
        file_type,
    )

    consolidated_directory = get_consolidated_path(
        campaign,
        month,
        file_type,
    )

    # ========================================================
    # CURRENT SELECTION
    # ========================================================

    st.success(
        f"Campaign: **{campaign}** | "
        f"Month: **{month}** | "
        f"File Type: **{file_type}**"
    )

    st.write(
        f"**Searching:** `{processed_directory}`"
    )

    st.write(
        f"**Month folder:** "
        f"`{get_month_folder(month)}`"
    )

    # ========================================================
    # FIND FILES
    # ========================================================

    files = get_supported_files(
        processed_directory
    )

    if not files:
        st.warning(
            "No supported files were found "
            "in this location."
        )

        st.code(
            str(processed_directory),
            language="text",
        )

        if not processed_directory.exists():
            st.error(
                "The expected processed folder "
                "does not exist."
            )

        else:
            contents = list(
                processed_directory.iterdir()
            )

            if contents:
                st.write(
                    "Files currently in this folder:"
                )

                for item in contents:
                    st.write(
                        f"- `{item.name}`"
                    )

            else:
                st.write(
                    "The folder exists but is empty."
                )

        return

    # ========================================================
    # AVAILABLE FILES
    # ========================================================

    st.subheader(
        "Available Processed Files"
    )

    file_information = []

    for path in files:
        file_information.append(
            {
                "File": path.name,
                "Rows": get_row_count(path),
                "Size (MB)": round(
                    path.stat().st_size
                    / (1024 * 1024),
                    2,
                ),
            }
        )

    information_df = pl.DataFrame(
        file_information
    )

    st.dataframe(
        information_df.to_pandas(),
        width="stretch",
        hide_index=True,
    )

    # ========================================================
    # FILE SELECTION
    # ========================================================

    file_names = [
        path.name
        for path in files
    ]

    selected_names = st.multiselect(
        "Select files to consolidate",
        options=file_names,
        default=file_names,
        key="consolidator_selected_files",
    )

    selected_files = [
        path
        for path in files
        if path.name in selected_names
    ]

    if not selected_files:
        st.warning(
            "Please select at least one file."
        )
        return

    # ========================================================
    # SUMMARY
    # ========================================================

    total_rows = sum(
        get_row_count(path)
        for path in selected_files
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Selected Files",
            f"{len(selected_files):,}",
        )

    with col2:
        st.metric(
            "Total Rows",
            f"{total_rows:,}",
        )

    # ========================================================
    # EXPORT FORMAT
    # ========================================================

    export_format = st.selectbox(
        "Export Format",
        [
            "CSV",
            "Excel",
            "Parquet",
        ],
        index=0,
        key="consolidator_export_format",
    )

    # ========================================================
    # PREPARE AND STORE
    # ========================================================

    if not st.button(
        "Prepare and Store",
        type="primary",
        use_container_width=True,
        key="prepare_and_store",
    ):
        return

    progress = st.progress(0)

    try:

        dataframes = []

        # ====================================================
        # READ FILES
        # ====================================================

        for index, path in enumerate(
            selected_files
        ):

            st.write(
                f"Reading `{path.name}`..."
            )

            frame = read_file(path)

            frame = normalize_nested_columns(
                frame
            )

            dataframes.append(
                frame
            )

            progress.progress(
                int(
                    (
                        (index + 1)
                        / len(selected_files)
                    )
                    * 50
                )
            )

        if not dataframes:
            st.error(
                "No data could be loaded."
            )
            return

        # ====================================================
        # CONSOLIDATE
        # ====================================================

        st.write(
            "Consolidating datasets..."
        )

        consolidated = pl.concat(
            dataframes,
            how="diagonal_relaxed",
        )

        consolidated = (
            normalize_nested_columns(
                consolidated
            )
        )

        progress.progress(70)

        # ====================================================
        # RESULT
        # ====================================================

        st.success(
            f"Consolidation completed: "
            f"{consolidated.height:,} rows × "
            f"{consolidated.width:,} columns."
        )

        st.subheader(
            "Preview"
        )

        st.dataframe(
            consolidated.head(100).to_pandas(),
            width="stretch",
            hide_index=True,
        )

        # ====================================================
        # FILE NAME
        # ====================================================

        # IMPORTANT:
        # The filename now uses the SELECTED MONTH,
        # CURRENT YEAR, and SELECTED FILE TYPE.

        base_name = (
            f"{str(month).strip()} "
            f"{datetime.now().year} "
            f"Consolidated "
            f"{str(file_type).strip()}"
        )

        # Remove characters that are invalid in Windows filenames.
        base_name = (
            base_name
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace("*", "_")
            .replace("?", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )

        output_files = []

        # ====================================================
        # CSV
        # ====================================================

        if export_format == "CSV":

            csv_bytes = (
                consolidated
                .write_csv()
                .encode("utf-8")
            )

            output_name = (
                f"{base_name}.csv"
            )

            output_path = (
                consolidated_directory
                / output_name
            )

            output_path.write_bytes(
                csv_bytes
            )

            output_files.append(
                (
                    output_name,
                    csv_bytes,
                )
            )

        # ====================================================
        # PARQUET
        # ====================================================

        elif export_format == "Parquet":

            output_name = (
                f"{base_name}.parquet"
            )

            output_path = (
                consolidated_directory
                / output_name
            )

            consolidated.write_parquet(
                output_path,
                compression="zstd",
            )

            output_files.append(
                (
                    output_name,
                    output_path.read_bytes(),
                )
            )

        # ====================================================
        # EXCEL
        # ====================================================

        elif export_format == "Excel":

            output_name = (
                f"{base_name}.xlsx"
            )

            output_path = (
                consolidated_directory
                / output_name
            )

            max_rows = 1_048_575

            with tempfile.NamedTemporaryFile(
                suffix=".xlsx",
                delete=False,
            ) as temporary_file:

                temporary_path = Path(
                    temporary_file.name
                )

            try:

                with pl.ExcelWriter(
                    temporary_path
                ) as writer:

                    sheet_number = 1

                    for start in range(
                        0,
                        consolidated.height,
                        max_rows,
                    ):

                        chunk = consolidated.slice(
                            start,
                            max_rows,
                        )

                        chunk.write_excel(
                            workbook=writer,
                            worksheet=(
                                f"Data {sheet_number}"
                            ),
                            autofit=False,
                        )

                        sheet_number += 1

                excel_bytes = (
                    temporary_path.read_bytes()
                )

                output_path.write_bytes(
                    excel_bytes
                )

                output_files.append(
                    (
                        output_name,
                        excel_bytes,
                    )
                )

            finally:

                if temporary_path.exists():
                    temporary_path.unlink()

        progress.progress(100)

        # ====================================================
        # STORED
        # ====================================================

        st.success(
            f"Stored successfully: "
            f"`{output_path}`"
        )

        # ====================================================
        # DOWNLOAD
        # ====================================================

        output_name, output_bytes = (
            output_files[0]
        )

        if export_format == "CSV":

            mime_type = "text/csv"

        elif export_format == "Excel":

            mime_type = (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )

        else:

            mime_type = (
                "application/octet-stream"
            )

        st.download_button(
            f"Download {output_name}",
            data=output_bytes,
            file_name=output_name,
            mime=mime_type,
            use_container_width=True,
            key="download_consolidated",
        )

        # ====================================================
        # ZIP
        # ====================================================

        zip_bytes = create_zip(
            output_files
        )

        zip_name = (
            f"{base_name}.zip"
        )

        st.download_button(
            f"Download ZIP ({zip_name})",
            data=zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            use_container_width=True,
            key="download_consolidated_zip",
        )

    except Exception as error:

        progress.progress(100)

        st.error(
            f"Unable to consolidate datasets: "
            f"{error}"
        )

        st.exception(error)