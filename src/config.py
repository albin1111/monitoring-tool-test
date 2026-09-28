from pathlib import Path


# ============================================================
# BASE DIRECTORIES
# ============================================================

DATA_DIRECTORY = Path("data")

STAGING_DIRECTORY = DATA_DIRECTORY / "staging"
UPLOAD_DIRECTORY = DATA_DIRECTORY / "uploads"
PROCESSED_DIRECTORY = DATA_DIRECTORY / "processed"
CONSOLIDATED_DIRECTORY = DATA_DIRECTORY / "consolidated"

DATABASE_PATH = DATA_DIRECTORY / "monitoring.duckdb"


for directory in (
    DATA_DIRECTORY,
    STAGING_DIRECTORY,
    UPLOAD_DIRECTORY,
    PROCESSED_DIRECTORY,
    CONSOLIDATED_DIRECTORY,
):
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# CAMPAIGNS
# ============================================================

CAMPAIGNS = {
    "sbc_b2": "SBC B2",
    "sbc_b4": "SBC B4",
    "sbc_al_b2": "SBC AL B2",
    "sbc_al_b6": "SBC AL B6",
    "sbc_recovery": "SBC Recovery",
    "sbc_al_recovery": "SBC AL Recovery",
    "sbc_wbs": "SBC WBS",
    "sbc_geox": "SBC Geox",
    "sbc_insurance": "SBC Insurance",
    "sbc_homeloan": "SBC Homeloan",
}


# ============================================================
# MONTHS
# ============================================================

MONTHS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


# ============================================================
# FILE TYPES
# ============================================================

FILE_TYPES = {
    "dar": "DAR",
    "drr": "DRR",
    "payment": "Payment",
    "field": "Field",
    "attendance": "Attendance",
    "other": "Other",
}


# ============================================================
# ALLOWED FILE EXTENSIONS
# ============================================================

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".xlsm"
    ".parquet",
}


# ============================================================
# UPLOAD SETTINGS
# ============================================================

MAX_UPLOAD_BYTES = 500 * 1024 * 1024

MAX_COLUMNS = 5_000

MAX_COLUMN_NAME_LENGTH = 255

UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024


# ============================================================
# RESERVED COLUMNS
# ============================================================

RESERVED_COLUMNS = {
    "_meta_import_id",
    "_meta_source_file",
    "_meta_campaign_id",
    "_meta_campaign_name",
    "_meta_reporting_year",
    "_meta_reporting_month",
    "_meta_reporting_period",
    "_meta_imported_at",
}


# ============================================================
# FOLDER NAME HELPERS
# ============================================================

def safe_campaign_name(campaign: str) -> str:
    """
    Convert campaign name into a safe folder name.

    Example:
        SBC B2 -> SBC_B2
        SBC AL B2 -> SBC_AL_B2
    """

    return (
        str(campaign)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def safe_file_type_name(file_type: str) -> str:
    """
    Convert file type into a safe folder name.

    Example:
        DAR -> DAR
        Account Allocation -> Account_Allocation
    """

    if not file_type:
        return "Other"

    return (
        str(file_type)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def get_month_folder(month: str) -> str:
    """
    Convert month name into:

        August -> 08_August
    """

    month = str(month).strip()

    for month_number, month_name in MONTHS.items():

        if month_name == month:
            return (
                f"{month_number:02d}_{month_name}"
            )

    raise ValueError(
        f"Invalid month: {month}"
    )


# ============================================================
# DIRECTORY HELPERS
# ============================================================

def get_upload_directory(
    campaign: str,
    month: str,
    file_type: str,
) -> Path:

    directory = (
        UPLOAD_DIRECTORY
        / safe_campaign_name(campaign)
        / get_month_folder(month)
        / safe_file_type_name(file_type)
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def get_processed_directory(
    campaign: str,
    month: str,
    file_type: str,
) -> Path:

    directory = (
        PROCESSED_DIRECTORY
        / safe_campaign_name(campaign)
        / get_month_folder(month)
        / safe_file_type_name(file_type)
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def get_consolidated_directory(
    campaign: str,
    month: str,
    file_type: str,
) -> Path:

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