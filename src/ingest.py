from pathlib import Path
from io import BytesIO

import msoffcrypto
import polars as pl

from src.config import (
    CAMPAIGNS,
    MONTHS,
    FILE_TYPES,
    ALLOWED_EXTENSIONS,
    get_upload_directory,
    get_processed_directory,
    get_consolidated_directory,
)


# ============================================================
# DISPLAY OPTIONS
# ============================================================

CAMPAIGN_OPTIONS = list(CAMPAIGNS.values())
MONTH_OPTIONS = list(MONTHS.values())
FILE_TYPE_OPTIONS = list(FILE_TYPES.values())


# ============================================================
# NAME / PATH HELPERS
# ============================================================

def safe_campaign_name(campaign: str) -> str:
    return (
        str(campaign)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def safe_file_type_name(file_type: str) -> str:
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
    month = str(month).strip()

    for month_number, month_name in MONTHS.items():
        if month_name == month:
            return f"{month_number:02d}_{month_name}"

    raise ValueError(f"Invalid month: {month}")


# ============================================================
# COLUMN NORMALIZATION
# ============================================================

def normalize_columns(
    df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Normalize column names.

    - Converts names to strings
    - Removes leading/trailing spaces
    - Replaces empty names
    - Makes duplicate names unique
    """

    new_names = []
    used_names = {}

    for index, column in enumerate(df.columns):
        name = str(column).strip()

        if not name:
            name = f"column_{index + 1}"

        if name in used_names:
            used_names[name] += 1
            name = f"{name}_{used_names[name]}"
        else:
            used_names[name] = 0

        new_names.append(name)

    rename_mapping = dict(
        zip(df.columns, new_names)
    )

    return df.rename(rename_mapping)


# ============================================================
# EXCEL DATA TYPE NORMALIZATION
# ============================================================

def normalize_excel_dtypes(
    df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Normalize unusual Excel data types.

    Converts List and Struct columns into strings so
    they can safely be written to CSV/Parquet and
    consolidated with other files.
    """

    expressions = []

    for column, dtype in df.schema.items():

        if isinstance(dtype, pl.List):
            expressions.append(
                pl.col(column)
                .list.eval(
                    pl.element().cast(pl.String)
                )
                .list.join(", ")
                .alias(column)
            )

        elif isinstance(dtype, pl.Struct):
            expressions.append(
                pl.col(column)
                .cast(pl.String)
                .alias(column)
            )

    if expressions:
        df = df.with_columns(expressions)

    return df


# ============================================================
# ROW CLEANING
# ============================================================

def drop_orphan_rows(
    df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Remove rows that only contain a value in the first column.

    A row with data in the first cell and blanks everywhere
    else is treated as a stray record and excluded.
    """

    if df.width <= 1:
        return df

    first_column = df.columns[0]

    other_columns = [
        column
        for column in df.columns
        if column != first_column
    ]

    has_other_data = pl.any_horizontal(
        [
            pl.col(column)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .is_not_null()
            & (
                pl.col(column)
                .cast(pl.String, strict=False)
                .str.strip_chars()
                != ""
            )
            for column in other_columns
        ]
    )

    return df.filter(has_other_data)


# ============================================================
# EXCEL FILE DETECTION
# ============================================================

def is_excel_file(path: Path) -> bool:
    return Path(path).suffix.lower() in {
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
    }


# ============================================================
# EXCEL ENCRYPTION DETECTION
# ============================================================

def is_excel_encrypted(path: Path) -> bool:
    """
    Determine whether an Excel workbook is encrypted.
    """

    path = Path(path)

    if not is_excel_file(path):
        return False

    try:
        with path.open("rb") as file:
            office_file = msoffcrypto.OfficeFile(file)
            return bool(office_file.is_encrypted())

    except Exception as error:
        raise ValueError(
            f"Unable to inspect Excel encryption for "
            f"'{path.name}': {error}"
        ) from error


# ============================================================
# EXCEL DECRYPTION
# ============================================================

def decrypt_excel_file(
    path: Path,
    password: str,
) -> BytesIO:
    """
    Decrypt a password-protected Excel workbook.

    The original file is not modified.
    The decrypted workbook remains in memory.
    """

    path = Path(path)

    # Do not strip the password.
    # Spaces may legitimately be part of the password.
    if password is None or password == "":
        raise ValueError(
            f"'{path.name}' is password protected. "
            f"No password was supplied."
        )

    decrypted_file = BytesIO()

    try:
        with path.open("rb") as file:

            office_file = msoffcrypto.OfficeFile(file)

            office_file.load_key(
                password=password,
                verify_password=True,
            )

            office_file.decrypt(
                decrypted_file
            )

    except Exception as error:
        raise ValueError(
            f"Unable to decrypt '{path.name}'. "
            f"Please verify the password. "
            f"Details: {error}"
        ) from error

    decrypted_file.seek(0)

    return decrypted_file


# ============================================================
# EXCEL READER
# ============================================================

def read_workbook_source(
    source,
    extension: str,
) -> pl.DataFrame:
    """
    Read an Excel workbook with the calamine engine.

    XLSB workbooks are read by sheet index because their
    sheet names are not reliably available to Polars.
    """

    extension = str(extension).lower()

    if extension == ".xlsb":

        try:
            return pl.read_excel(
                source=source,
                engine="calamine",
                infer_schema_length=0,
            )

        except Exception:
            return pl.read_excel(
                source=source,
                engine="calamine",
                sheet_id=0,
                infer_schema_length=0,
            )

    return pl.read_excel(
        source=source,
        engine="calamine",
        infer_schema_length=0,
    )

def read_excel_file(
    path: Path,
    password: str | None = None,
) -> pl.DataFrame:
    """
    Read XLS, XLSX, and XLSM files.

    Automatically decrypts password-protected
    Excel workbooks.
    """

    path = Path(path)

    encrypted = is_excel_encrypted(path)

    # --------------------------------------------------------
    # PASSWORD-PROTECTED EXCEL
    # --------------------------------------------------------

    if encrypted:

        if password is None or password == "":
            raise ValueError(
                f"'{path.name}' is password protected. "
                f"Please enter the Excel password."
            )

        decrypted_file = decrypt_excel_file(
            path=path,
            password=password,
        )

        df = read_workbook_source(
            source=decrypted_file,
            extension=path.suffix.lower(),
        )

    # --------------------------------------------------------
    # NORMAL EXCEL
    # --------------------------------------------------------

    else:

        df = read_workbook_source(
            source=path,
            extension=path.suffix.lower(),
        )

    # --------------------------------------------------------
    # NORMALIZE EXCEL TYPES
    # --------------------------------------------------------

    df = normalize_excel_dtypes(df)

    return df


# ============================================================
# CSV READER
# ============================================================

def read_csv_file(
    path: Path,
) -> pl.DataFrame:
    """
    Read a CSV file.

    Uses a larger schema inference window to reduce
    dtype inference issues on large datasets.
    """

    return pl.read_csv(
        path,
        infer_schema_length=10_000,
        ignore_errors=False,
    )


# ============================================================
# PARQUET READER
# ============================================================

def read_parquet_file(
    path: Path,
) -> pl.DataFrame:
    """
    Read a Parquet file.
    """

    return pl.read_parquet(path)


# ============================================================
# MAIN FILE READER
# ============================================================

def read_tabular_file(
    path: Path,
    password: str | None = None,
) -> pl.DataFrame:
    """
    Read CSV, Excel, or Parquet.

    Password is only used for Excel files.
    """

    path = Path(path)

    validate_tabular_file(path)

    extension = path.suffix.lower()

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if extension == ".csv":

        df = read_csv_file(path)

    # --------------------------------------------------------
    # EXCEL
    # --------------------------------------------------------

    elif extension in {
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
    }:

        df = read_excel_file(
            path=path,
            password=password,
        )

    # --------------------------------------------------------
    # PARQUET
    # --------------------------------------------------------

    elif extension == ".parquet":

        df = read_parquet_file(path)

    else:

        raise ValueError(
            f"Unsupported file format: {extension}"
        )

    # --------------------------------------------------------
    # NORMALIZE COLUMN NAMES
    # --------------------------------------------------------

    df = normalize_columns(df)

    # --------------------------------------------------------
    # DROP ORPHAN ROWS
    # --------------------------------------------------------

    df = drop_orphan_rows(df)

    return df


# ============================================================
# LAZY FILE READER
# ============================================================

def scan_tabular_file(
    path: Path,
    password: str | None = None,
):
    """
    Read files lazily when possible.

    Parquet and CSV are scanned lazily.

    Excel is read into memory because Excel does not
    provide the same lazy scanning behavior.
    """

    path = Path(path)

    validate_tabular_file(path)

    extension = path.suffix.lower()

    # --------------------------------------------------------
    # PARQUET
    # --------------------------------------------------------

    if extension == ".parquet":

        return pl.scan_parquet(path)

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if extension == ".csv":

        return pl.scan_csv(
            path,
            infer_schema_length=10_000,
        )

    # --------------------------------------------------------
    # EXCEL
    # --------------------------------------------------------

    if extension in {
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
    }:

        return (
            read_excel_file(
                path,
                password=password,
            )
            .lazy()
        )

    raise ValueError(
        f"Unsupported file format: {extension}"
    )


# ============================================================
# FILE VALIDATION
# ============================================================

def validate_tabular_file(
    path: Path,
) -> None:
    """
    Validate that the file exists and uses a supported
    tabular file extension.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {path}"
        )

    extension = path.suffix.lower()

    supported_extensions = {
        ".csv",
        ".xlsx",
        ".xls",
        ".xlsm",
        ".xlsb",
        ".parquet",
    }

    if extension not in supported_extensions:
        raise ValueError(
            f"Unsupported file format: {extension}. "
            f"Supported formats: "
            f"{', '.join(sorted(supported_extensions))}"
        )


# ============================================================
# FILE INFORMATION
# ============================================================

def get_file_info(
    path: Path,
) -> dict:
    path = Path(path)

    validate_tabular_file(path)

    size_bytes = path.stat().st_size

    return {
        "name": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": size_bytes,
        "size_mb": round(
            size_bytes / 1024 / 1024,
            2,
        ),
    }


# ============================================================
# DIRECTORY HELPERS
# ============================================================

def get_upload_path(
    campaign: str,
    month: str,
    file_type: str,
) -> Path:
    return get_upload_directory(
        campaign,
        month,
        file_type,
    )


def get_processed_path(
    campaign: str,
    month: str,
    file_type: str,
) -> Path:
    return get_processed_directory(
        campaign,
        month,
        file_type,
    )


def get_consolidated_path(
    campaign: str,
    month: str,
    file_type: str,
) -> Path:
    return get_consolidated_directory(
        campaign,
        month,
        file_type,
    )