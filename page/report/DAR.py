import streamlit as st
import pandas as pd
import openpyxl
import msoffcrypto
import re
import random
from io import BytesIO
from pathlib import Path
from datetime import datetime, date, time
from zipfile import ZipFile


# ============================================================
# PATHS / CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
REFERENCE_DIRECTORY = BASE_DIR / "reference"

CLIENT_CONFIG = {
    "SBC AUTO LOAN": {
        "reference": "SBC AL B6",
        "folder": "SBC_AL_B6",
    },
    "SBC AUTO LOAN CURING": {
        "reference": "SBC AL B2",
        "folder": "SBC_AL_B2",
    },
    "SBC AUTO LOAN RECOVERY": {
        "reference": "SBC AL Recovery",
        "folder": "SBC_AL_Recovery",
    },
    "SBC CARDS CURING B2": {
        "reference": "SBC B2",
        "folder": "SBC_B2",
    },
    "SBC CURING B4": {
        "reference": "SBC B4",
        "folder": "SBC_B4",
    },
    "SBC CARDS CARDS & LOAN L6": {
        "reference": "SBC Recovery",
        "folder": "SBC_Recovery",
    },
    "SBC CARDS RECOV L1": {
        "reference": "SBC Recovery",
        "folder": "SBC_Recovery",
    },
    "SBC PL RECOV L1": {
        "reference": "SBC Recovery",
        "folder": "SBC_Recovery",
    },
    "SBC HOMELOAN": {
        "reference": "SBC Homeloan",
        "folder": "SBC_Homeloan",
    },
}


# ============================================================
# UI STYLES
# ============================================================

def apply_dar_styles():
    st.markdown(
        """
        <style>
        /* ====================================================
           DAR PAGE ONLY
           These styles are intentionally scoped to .dar-page
           so sidebar buttons are NOT affected.
           ==================================================== */

        .dar-page div.stButton > button,
        .dar-page div.stDownloadButton > button {
            width: auto !important;
            min-width: 120px !important;
            padding: 0.25rem 0.8rem !important;
            font-size: 0.85rem !important;
            min-height: 32px !important;
        }

        .dar-page div[data-testid="stFormSubmitButton"] > button {
            width: auto !important;
            min-width: 120px !important;
            padding: 0.25rem 0.8rem !important;
            font-size: 0.85rem !important;
            min-height: 32px !important;
        }

        .dar-page .dar-section {
            margin-top: 0.5rem;
            margin-bottom: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def normalize_column_name(value):
    return re.sub(
        r"\s+",
        " ",
        str(value).strip(),
    ).lower()


def find_column(df, *names):
    normalized = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for name in names:
        key = normalize_column_name(name)

        if key in normalized:
            return normalized[key]

    for col in df.columns:
        col_key = normalize_column_name(col)

        for name in names:
            name_key = normalize_column_name(name)

            if name_key in col_key:
                return col

    return None


def clean_value(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


# ============================================================
# SAFE DATE / TIME FUNCTIONS
# ============================================================

def is_blank_datetime(value):
    if value is None:
        return True

    if value == "":
        return True

    try:
        result = pd.isna(value)

        if isinstance(result, bool):
            return result

    except Exception:
        pass

    return False


def format_date(value):
    if is_blank_datetime(value):
        return ""

    try:
        if isinstance(value, pd.Timestamp):
            if pd.isna(value):
                return ""

            return value.strftime("%m/%d/%Y")

        if isinstance(value, datetime):
            return value.strftime("%m/%d/%Y")

        if isinstance(value, date):
            return value.strftime("%m/%d/%Y")

        parsed = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(parsed):
            return ""

        return parsed.strftime("%m/%d/%Y")

    except Exception:
        return ""


def format_time_parts(value):
    if is_blank_datetime(value):
        return "", "", "", ""

    try:
        if isinstance(value, pd.Timestamp):
            if pd.isna(value):
                return "", "", "", ""

            value = value.to_pydatetime()

        if isinstance(value, datetime):
            hour = value.hour
            minute = value.minute
            second = value.second

        elif isinstance(value, time):
            hour = value.hour
            minute = value.minute
            second = value.second

        else:
            parsed = pd.to_datetime(
                value,
                errors="coerce",
            )

            if pd.isna(parsed):
                return "", "", "", ""

            hour = parsed.hour
            minute = parsed.minute
            second = parsed.second

        am_pm = "am" if hour < 12 else "pm"

        display_hour = hour % 12

        if display_hour == 0:
            display_hour = 12

        return (
            f"{display_hour:02d}",
            f"{minute:02d}",
            f"{second:02d}",
            am_pm,
        )

    except Exception:
        return "", "", "", ""


def format_amount(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if isinstance(value, str):
        value = value.replace(",", "").strip()

        if not value:
            return ""

    try:
        return f"{float(value):.2f}"

    except Exception:
        return ""


# ============================================================
# EXCEL / PASSWORD HANDLING
# ============================================================

def is_ooxml_excel(data):
    if not data:
        return False

    if not data.startswith(b"PK"):
        return False

    try:
        with ZipFile(BytesIO(data)) as z:
            names = set(z.namelist())

            return (
                "[Content_Types].xml" in names
                and (
                    "xl/workbook.xml" in names
                    or "xl/workbook.bin" in names
                )
            )

    except Exception:
        return False


def detect_excel_format(data):
    if is_ooxml_excel(data):
        return "xlsx"

    if data[:8] == (
        b"\xD0\xCF\x11\xE0"
        b"\xA1\xB1\x1A\xE1"
    ):
        return "xls"

    if data[:4] == b"PK\x03\x04":
        return "xlsx"

    return None


def is_encrypted_excel(data):
    try:
        office_file = msoffcrypto.OfficeFile(
            BytesIO(data)
        )

        return office_file.is_encrypted()

    except Exception:
        return False


def decrypt_excel(data, password=""):
    try:
        office_file = msoffcrypto.OfficeFile(
            BytesIO(data)
        )

    except Exception as exc:
        raise ValueError(
            "Unable to inspect the Excel workbook."
        ) from exc

    try:
        encrypted = office_file.is_encrypted()

    except Exception:
        encrypted = False

    if not encrypted:
        return data

    password = (password or "").strip()

    if not password:
        password = "SPM"

    decrypted = BytesIO()

    try:
        office_file.load_key(
            password=password
        )

        office_file.decrypt(
            decrypted
        )

    except Exception as exc:
        raise ValueError(
            "The masterlist is password-protected "
            "and could not be opened. "
            "If the password field was blank, "
            "the automatic password SPM was attempted."
        ) from exc

    return decrypted.getvalue()


def read_masterlist_bytes(
    data,
    filename,
    password="",
):
    if not data:
        raise ValueError(
            "The masterlist file is empty."
        )

    if is_encrypted_excel(data):
        data = decrypt_excel(
            data,
            password=password,
        )

    file_format = detect_excel_format(data)

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if file_format == "xlsx":
        actual_extension = ".xlsx"

    elif file_format == "xls":
        actual_extension = ".xls"

    else:
        actual_extension = extension

    try:
        if actual_extension in [
            ".xlsx",
            ".xlsm",
        ]:

            df = pd.read_excel(
                BytesIO(data),
                engine="openpyxl",
            )

        elif actual_extension == ".xls":

            df = pd.read_excel(
                BytesIO(data),
                engine="xlrd",
            )

        else:

            try:
                df = pd.read_excel(
                    BytesIO(data),
                    engine="openpyxl",
                )

            except Exception:
                df = pd.read_excel(
                    BytesIO(data),
                    engine="xlrd",
                )

    except Exception as exc:
        raise ValueError(
            f"Unable to process masterlist "
            f"'{filename}'. Please make sure it "
            f"is a valid Excel workbook. "
            f"Original error: {exc}"
        ) from exc

    if df.empty:
        raise ValueError(
            "The masterlist contains no data."
        )

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    return df


# ============================================================
# PATH HELPERS
# ============================================================

def get_client_config(client):
    config = CLIENT_CONFIG.get(client)

    if not config:
        raise ValueError(
            f"No configuration was found "
            f"for client '{client}'."
        )

    return config


def get_client_reference_folder(client):
    config = get_client_config(client)

    return (
        REFERENCE_DIRECTORY
        / config["reference"]
    )


def get_client_masterlist_folder(client):
    folder = (
        get_client_reference_folder(client)
        / "masterlist"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return folder


def get_dar_reference_path(client):
    reference_folder = (
        get_client_reference_folder(client)
    )

    candidates = [
        reference_folder / "DAR Reference.xlsm",
        reference_folder / "DAR Reference.xlsx",
        reference_folder / "DAR Reference.xls",
    ]

    for path in candidates:
        if path.exists():
            return path

    for path in reference_folder.glob(
        "DAR Reference.*"
    ):
        if path.is_file():
            return path

    return None


def get_masterlist_date_folder(
    client,
    dar_date,
):
    folder = (
        get_client_masterlist_folder(client)
        / dar_date.strftime("%Y-%m-%d")
    )

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return folder


def save_uploaded_masterlist(
    client,
    dar_date,
    filename,
    data,
    password="",
):
    df = read_masterlist_bytes(
        data,
        filename,
        password=password,
    )

    folder = get_masterlist_date_folder(
        client,
        dar_date,
    )

    output_path = (
        folder / "masterlist.xlsx"
    )

    df.to_excel(
        output_path,
        index=False,
    )

    return output_path, df


def find_masterlist(
    client,
    dar_date,
):
    root = get_client_masterlist_folder(
        client
    )

    date_folder = (
        root
        / dar_date.strftime("%Y-%m-%d")
    )

    if date_folder.exists():

        preferred = [
            date_folder / "masterlist.xlsx",
            date_folder / "masterlist.xlsm",
            date_folder / "masterlist.xls",
        ]

        for path in preferred:
            if path.exists():
                return path

        for path in date_folder.iterdir():

            if (
                path.is_file()
                and path.suffix.lower()
                in [
                    ".xlsx",
                    ".xlsm",
                    ".xls",
                ]
            ):
                return path

    date_text = dar_date.strftime(
        "%Y-%m-%d"
    )

    for path in root.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in [
            ".xlsx",
            ".xlsm",
            ".xls",
        ]:
            continue

        if date_text in path.name:
            return path

    return None


def read_masterlist_file(
    path,
    password="",
):
    data = path.read_bytes()

    return read_masterlist_bytes(
        data,
        path.name,
        password=password,
    )


# ============================================================
# MASTERLIST
# ============================================================

def format_phone_number(value):
    """
    Format a contact number as a plain digit string.

    Excel often reads a number as 900000000.0 or 9000000000.0,
    which must become 09000000000.
    """

    text = clean_value(value)

    if not text:
        return ""

    # Drop a trailing decimal portion, for example .0
    if "." in text:
        text = text.split(".", 1)[0]

    # Keep digits only.
    digits = re.sub(r"\D", "", text)

    if not digits:
        return ""

    # Remove a country code written as 63.
    if len(digits) > 11 and digits.startswith("63"):
        digits = digits[2:]

    # A 10-digit local number is missing its leading zero.
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits

    return digits

def prepare_masterlist(df):
    # "Account Key" is the database's own account column and is
    # tried before the generic DRR-style names.
    account_col = find_column(
        df,
        "Account Key",
        "Account Number",
        "Account No",
        "Account No.",
        "Account",
        "ACCOUNT NUMBER",
        "ACCOUNT NO",
    )

    if not account_col:
        raise ValueError(
            "The masterlist does not contain "
            "an Account Number column."
        )

    df = df.copy()

    df["_DAR_ACCOUNT"] = (
        df[account_col]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    return df


def build_masterlist_lookup(df):
    bucket_col = find_column(
        df,
        "Bucket/Level",
        "Bucket",
        "Level",
    )

    # Mobile numbers come from Mobile (01) through Mobile (10),
    # with the Phone (nn) columns as a fallback.
    mobile_columns = []
    phone_columns = []

    for number in range(1, 11):

        label = f"{number:02d}"

        for candidate in [
            f"Mobile ({label})",
            f"Mobile Number ({label})",
            f"Mobile {label}",
        ]:

            column = find_column(df, candidate)

            if column and column not in mobile_columns:
                mobile_columns.append(column)

        for candidate in [
            f"Phone ({label})",
            f"Phone {label}",
        ]:

            column = find_column(df, candidate)

            if column and column not in phone_columns:
                phone_columns.append(column)

    mobile_column = find_column(df, "Mobile Number")

    if mobile_column and mobile_column not in mobile_columns:
        mobile_columns.append(mobile_column)

    # Contact Number is kept for Skip touchpoints only.
    contact_column = find_column(
        df,
        "Contact Number",
        "Contact No",
        "Contact No.",
    )

    # Prefer the database's Account Key when resolving the lookup,
    # because that is the column the DRR account is matched against.
    account_key_col = find_column(
        df,
        "Account Key",
        "_DAR_ACCOUNT",
    )

    address_columns = [
        find_column(df, "Address (01)"),
        find_column(df, "Address (02)"),
        find_column(df, "Address 01"),
        find_column(df, "Home Address"),
        find_column(df, "Present Address"),
        find_column(df, "Mailing Address"),
        find_column(df, "Residence Address"),
        find_column(df, "Address"),
    ]

    address_columns = [
        col
        for col in address_columns
        if col
    ]

    email_columns = [
        find_column(df, "Email (01)"),
        find_column(df, "Email (02)"),
        find_column(df, "Email 01"),
        find_column(df, "Email Address"),
        find_column(df, "E-mail"),
        find_column(df, "EmailAddress"),
        find_column(df, "Email"),
    ]

    email_columns = [
        col
        for col in email_columns
        if col
    ]

    lookup = {}

    for _, row in df.iterrows():

        if account_key_col:
            account = clean_value(
                row.get(account_key_col)
            )
        else:
            account = clean_value(
                row.get("_DAR_ACCOUNT")
            )

        if not account:
            continue

        bucket = ""

        if bucket_col:
            bucket = clean_value(
                row.get(bucket_col)
            )

        address = ""

        for col in address_columns:

            value = clean_value(
                row.get(col)
            )

            if value:
                address = value
                break

        email = ""

        for col in email_columns:

            value = clean_value(
                row.get(col)
            )

            if value:
                email = value
                break

        mobiles = []

        for col in mobile_columns:

            formatted = format_phone_number(
                row.get(col)
            )

            if formatted and formatted not in mobiles:
                mobiles.append(formatted)

        phones = []

        for col in phone_columns:

            formatted = format_phone_number(
                row.get(col)
            )

            if formatted and formatted not in phones:
                phones.append(formatted)

        # Mobile (01)-based values win; Phone (01) is the fallback.
        mobile = mobiles[0] if mobiles else ""
        phone = ""

        if mobiles:
            phone = mobiles[0]
        elif phones:
            phone = phones[0]

        contact_number_source = ""

        if contact_column:
            contact_number_source = format_phone_number(
                row.get(contact_column)
            )

        record = {
            "bucket": bucket,
            "address": address,
            "email": email,
            "phone": phone,
            "mobile": mobile,
            "phones": phones,
            "mobiles": mobiles,
            "contact_number": contact_number_source,
        }

        lookup[account] = record

        # Also index the DRR-normalized account when it differs.
        normalized = re.sub(
            r"\.0+$",
            "",
            account,
        )

        if normalized and normalized != account:
            lookup[normalized] = record

    return lookup


# ============================================================
# DAR REFERENCE
# ============================================================

def read_dar_reference(path):
    if not path.exists():
        raise ValueError(
            f"DAR Reference was not found: {path}"
        )

    try:
        keep_vba = (
            path.suffix.lower() == ".xlsm"
        )

        wb = openpyxl.load_workbook(
            filename=path,
            keep_vba=keep_vba,
            data_only=False,
            read_only=False,
        )

    except Exception as exc:
        raise ValueError(
            f"Unable to open DAR Reference "
            f"'{path.name}': {exc}"
        ) from exc

    if len(wb.worksheets) < 2:
        raise ValueError(
            f"DAR Reference '{path.name}' "
            f"must contain at least 2 worksheets. "
            f"Found {len(wb.worksheets)}."
        )

    # --------------------------------------------------------
    # FIND ACTIONS / ACTION
    # --------------------------------------------------------

    action_ws = None

    for ws in wb.worksheets:

        if ws.title.strip().lower() in [
            "action",
            "actions",
        ]:
            action_ws = ws
            break

    if action_ws is None:
        action_ws = wb.worksheets[0]

    # --------------------------------------------------------
    # FIND CODES
    # --------------------------------------------------------

    codes_ws = None

    for ws in wb.worksheets:

        if ws.title.strip().lower() == "codes":
            codes_ws = ws
            break

    if codes_ws is None:
        codes_ws = wb.worksheets[1]

    # --------------------------------------------------------
    # RENAME ACTIONS TO ACTION
    # --------------------------------------------------------

    if action_ws.title != "Action":

        if (
            "Action" in wb.sheetnames
            and wb["Action"] != action_ws
        ):
            wb["Action"].title = "__OLD_ACTION__"

        action_ws.title = "Action"

    # --------------------------------------------------------
    # RENAME CODES TO CODES
    # --------------------------------------------------------

    if codes_ws.title != "Codes":

        if (
            "Codes" in wb.sheetnames
            and wb["Codes"] != codes_ws
        ):
            wb["Codes"].title = "__OLD_CODES__"

        codes_ws.title = "Codes"

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    if "Action" not in wb.sheetnames:
        raise ValueError(
            "Unable to identify the Action sheet."
        )

    if "Codes" not in wb.sheetnames:
        raise ValueError(
            "Unable to identify the Codes sheet."
        )

    return wb


def read_reference_sheet(path):
    try:
        df = pd.read_excel(
            path,
            sheet_name="Reference",
            engine="openpyxl",
        )

    except Exception as exc:
        raise ValueError(
            f"Unable to read the Reference sheet: {exc}"
        ) from exc

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    return df


def read_manpower_sheet(path):
    try:
        df = pd.read_excel(
            path,
            sheet_name="Manpower",
            engine="openpyxl",
        )

    except Exception as exc:
        raise ValueError(
            f"Unable to read the Manpower sheet: {exc}"
        ) from exc

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    return df


def build_reference_lookup(df):
    status_col = find_column(
        df,
        "Status",
    )

    action_code_col = find_column(
        df,
        "Action Code",
        "ActionCode",
        "Code",
    )

    result_col = find_column(
        df,
        "Result",
    )

    # The Touchpoint column is the authoritative source for the
    # action value. "Action" is kept only as a fallback.
    action_col = find_column(
        df,
        "Touchpoint",
        "Touch Point",
        "Action",
    )

    if not status_col:
        raise ValueError(
            "The DAR Reference Reference sheet "
            "does not contain a Status column."
        )

    lookup = {}

    for _, row in df.iterrows():

        status = clean_value(
            row.get(status_col)
        )

        if not status:
            continue

        lookup[status.lower()] = {
            "action_code": (
                clean_value(
                    row.get(action_code_col)
                )
                if action_code_col
                else ""
            ),
            "result": (
                clean_value(
                    row.get(result_col)
                )
                if result_col
                else ""
            ),
            "action": (
                clean_value(
                    row.get(action_col)
                )
                if action_col
                else ""
            ),
        }

    return lookup


def build_manpower_lookup(df):
    volare_col = find_column(
        df,
        "Volare",
    )

    code2_col = find_column(
        df,
        "Code2",
    )

    if not volare_col or not code2_col:
        return {}

    lookup = {}

    for _, row in df.iterrows():

        volare = clean_value(
            row.get(volare_col)
        )

        code2 = clean_value(
            row.get(code2_col)
        )

        if volare:
            lookup[volare.lower()] = code2

    return lookup


def lookup_reference_status(
    status,
    reference_lookup,
):
    status_clean = clean_value(status)

    if not status_clean:
        return {
            "action_code": "",
            "result": "",
            "action": "",
        }

    exact = reference_lookup.get(
        status_clean.lower()
    )

    if exact:
        return exact

    for key, value in reference_lookup.items():

        if status_clean.lower() in key:
            return value

    return {
        "action_code": "",
        "result": "",
        "action": "",
    }


# ============================================================
# DRR
# ============================================================

def normalize_drr(df):
    df = df.copy()

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    return df


def filter_drr_by_date(
    df,
    dar_date,
):
    date_col = find_column(
        df,
        "DRR Date",
        "DISPO DATE",
        "Action Date",
        "Date",
    )

    if not date_col:
        return df

    parsed_dates = pd.to_datetime(
        df[date_col],
        errors="coerce",
    )

    return df.loc[
        parsed_dates.dt.date == dar_date
    ].copy()


def normalize_account(value):
    """Normalize account values before comparing DRR and masterlist rows."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    value = str(value).strip()
    value = re.sub(r"\.0+$", "", value)

    return value


def filter_drr_by_masterlist(drr_df, masterlist_df):
    """Keep only DRR rows whose account exists in the masterlist."""
    drr_account_col = find_column(
        drr_df,
        "Account Number",
        "Account No",
        "Account No.",
        "Account",
        "ACCOUNT NUMBER",
        "ACCOUNT NO",
    )

    if not drr_account_col:
        raise ValueError(
            "The DRR file does not contain an Account Number column."
        )

    if "_DAR_ACCOUNT" not in masterlist_df.columns:
        masterlist_df = prepare_masterlist(masterlist_df)

    valid_accounts = {
        normalize_account(value)
        for value in masterlist_df["_DAR_ACCOUNT"]
        if normalize_account(value)
    }

    filtered_df = drr_df.copy()
    filtered_df["_DAR_MATCH_ACCOUNT"] = (
        filtered_df[drr_account_col]
        .map(normalize_account)
    )

    filtered_df = filtered_df.loc[
        filtered_df["_DAR_MATCH_ACCOUNT"].isin(valid_accounts)
    ].copy()

    return filtered_df.drop(
        columns=["_DAR_MATCH_ACCOUNT"]
    )


def load_uploaded_drr(uploaded_file):
    filename = uploaded_file.name

    data = uploaded_file.getvalue()

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if extension in [
        ".xlsx",
        ".xlsm",
    ]:

        df = pd.read_excel(
            BytesIO(data),
            engine="openpyxl",
        )

    elif extension == ".xls":

        df = pd.read_excel(
            BytesIO(data),
            engine="xlrd",
        )

    elif extension == ".csv":

        df = pd.read_csv(
            BytesIO(data)
        )

    elif extension == ".parquet":

        df = pd.read_parquet(
            BytesIO(data)
        )

    else:

        raise ValueError(
            f"Unsupported DRR format: {extension}"
        )

    return normalize_drr(df)


def load_consolidated_drr_files(client):
    config = get_client_config(client)

    root = (
        BASE_DIR
        / "data"
        / "consolidated"
        / config["folder"]
    )

    if not root.exists():
        return []

    files = []

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        if path.suffix.lower() not in [
            ".csv",
            ".xlsx",
            ".xls",
            ".parquet",
        ]:
            continue

        if "DRR" not in str(path).upper():
            continue

        files.append(path)

    return sorted(
        files,
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def read_consolidated_drr(path):
    extension = (
        path.suffix.lower()
    )

    if extension == ".csv":

        df = pd.read_csv(path)

    elif extension in [
        ".xlsx",
        ".xlsm",
    ]:

        df = pd.read_excel(
            path,
            engine="openpyxl",
        )

    elif extension == ".xls":

        df = pd.read_excel(
            path,
            engine="xlrd",
        )

    elif extension == ".parquet":

        df = pd.read_parquet(path)

    else:

        raise ValueError(
            f"Unsupported consolidated DRR format: {extension}"
        )

    return normalize_drr(df)


def excel_serial_to_time_parts(value):
    """
    Convert an Excel time value to HH, MM, SS, am/pm.

    Excel stores a bare time as a fraction of a day,
    for example 0.5256944444 for 12:37 pm.
    """

    try:
        fraction = float(value)
    except (TypeError, ValueError):
        return None

    if fraction != fraction:
        return None

    if fraction >= 1 or fraction < 0:
        fraction = fraction - int(fraction)

    total_seconds = int(round(fraction * 24 * 60 * 60)) % (24 * 60 * 60)

    hour = total_seconds // 3600
    minute = (total_seconds % 3600) // 60
    second = total_seconds % 60

    am_pm = "am" if hour < 12 else "pm"

    display_hour = hour % 12

    if display_hour == 0:
        display_hour = 12

    return (
        f"{display_hour:02d}",
        f"{minute:02d}",
        f"{second:02d}",
        am_pm,
    )


def parse_time_text(value):
    """
    Parse a time written as text: 12:37:05 PM, 12:37, 1:05 pm.
    """

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(".0:", ":")

    patterns = [
        r"^(\d{1,2}):(\d{1,2}):(\d{1,2})\s*([AaPp][Mm.]*)?$",
        r"^(\d{1,2}):(\d{1,2})\s*([AaPp][Mm.]*)?$",
    ]

    for pattern in patterns:

        match = re.match(pattern, text)

        if not match:
            continue

        groups = match.groups()

        hour = int(groups[0])
        minute = int(groups[1])
        second = int(groups[2]) if len(groups) == 4 else 0
        marker = groups[-1]

        if marker:

            marker = marker.strip().lower().replace(".", "")

            if marker.startswith("p") and hour < 12:
                hour += 12

            elif marker.startswith("a") and hour == 12:
                hour = 0

        if hour > 23 or minute > 59 or second > 59:
            return None

        am_pm = "am" if hour < 12 else "pm"

        display_hour = hour % 12

        if display_hour == 0:
            display_hour = 12

        return (
            f"{display_hour:02d}",
            f"{minute:02d}",
            f"{second:02d}",
            am_pm,
        )

    return None


def parse_drr_time_parts(record, drr_df, dispo_date_col=None):
    """
    Read each DRR record's Time field and return HH, MM, SS, am/pm.

    The Time field is the authoritative source and is handled
    whether it arrives as a datetime, a time, an Excel day
    fraction, or plain text.
    """

    time_col = find_column(
        drr_df,
        "Time",
        "Action Time",
        "DRR Time",
        "DISPO TIME",
        "Disposition Time",
    )

    if time_col:

        time_value = record.get(time_col)

        if not is_blank_datetime(time_value):

            if isinstance(time_value, (pd.Timestamp, datetime, time)):

                (
                    hour,
                    minute,
                    second,
                    ampm,
                ) = format_time_parts(time_value)

                if hour:
                    return (
                        hour,
                        minute,
                        second,
                        clean_value(ampm).lower(),
                    )

            if isinstance(time_value, (int, float)):

                parts = excel_serial_to_time_parts(time_value)

                if parts:
                    return parts

            parts = parse_time_text(time_value)

            if parts:
                return parts

    hour_col = find_column(
        drr_df,
        "HH",
        "Hour",
        "Hours",
        "Action Hour",
        "Action Time B",
    )
    minute_col = find_column(
        drr_df,
        "MM",
        "Minute",
        "Minutes",
        "Action Minute",
        "Action Time C",
    )
    second_col = find_column(
        drr_df,
        "SS",
        "Second",
        "Seconds",
        "Action Second",
        "Action Time D",
    )
    ampm_col = find_column(
        drr_df,
        "AM/PM",
        "AM PM",
        "AMPM",
        "Meridiem",
        "Action Time E",
    )

    separate_values = [
        clean_value(record.get(hour_col)) if hour_col else "",
        clean_value(record.get(minute_col)) if minute_col else "",
        clean_value(record.get(second_col)) if second_col else "",
        clean_value(record.get(ampm_col)) if ampm_col else "",
    ]

    if any(separate_values):

        hour, minute, second, ampm = separate_values

        hour = re.sub(r"\.0+$", "", hour)
        minute = re.sub(r"\.0+$", "", minute)
        second = re.sub(r"\.0+$", "", second)
        ampm = ampm.strip().lower().replace(".", "")

        if hour.isdigit():
            hour = hour.zfill(2)
        if minute.isdigit():
            minute = minute.zfill(2)
        if second.isdigit():
            second = second.zfill(2)

        if ampm in ["a", "am"]:
            ampm = "am"
        elif ampm in ["p", "pm"]:
            ampm = "pm"

        return hour, minute, second, ampm

    fallback_value = ""

    if dispo_date_col:
        fallback_value = record.get(dispo_date_col)

    hour, minute, second, ampm = format_time_parts(fallback_value)

    return (
        hour,
        minute,
        second,
        clean_value(ampm).lower(),
    )

def is_zero_or_blank(value):
    """
    True when a value is blank, zero, or otherwise not a real amount.
    """

    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = clean_value(value)

    if not text:
        return True

    # Remove currency symbols, commas, and spaces.
    text = text.replace(",", "").replace("PHP", "")
    text = text.replace("₱", "").strip()

    try:
        return float(text) == 0
    except Exception:
        return False


# ============================================================
# TOUCHPOINT REQUIREMENTS
# ============================================================

REQUIRED_TOUCHPOINTS = {
    "CALL": 20,
    "SMS": 4,
    "EMAIL": 4,
    "SKIP": 1,
}

# Action Code and Result written on each added record.
TOUCHPOINT_TEMPLATES = {
    "EMAIL": [
        {
            "action_code": "Email Sent",
            "result": "Email - Sent",
            "write_up": "EMAIL SENT",
        },
    ],
    "SMS": [
        {
            "action_code": "SMS Sent",
            "result": "SMS - Sent",
            "write_up": "SMS SENT",
        },
    ],
    "SKIP": [
        {
            "action_code": "Manual - ACA Action",
            "result": "Skips - Negative",
            "write_up": "No SocMed found in internet.",
        },
    ],
    "CALL": [
        {
            "action_code": "No Answer",
            "result": "No Connect - KOR (Keeps On Ringing)",
            "write_up": "Ringing No Answer",
        },
        {
            "action_code": "No Answer",
            "result": "No Connect - KOR (Keeps On Ringing)",
            "write_up": "Dropped Call",
        },
        {
            "action_code": "No Answer",
            "result": "No Connect - KOR (Keeps On Ringing)",
            "write_up": "KOR",
        },
        {
            "action_code": "Callout - System Announcement",
            "result": "No Connect - CBR (Cannot Be Reached)",
            "write_up": "CBR",
        },
    ],
}


def random_action_time():
    """
    Return HH, MM, SS, am/pm for a random time between
    8:00 AM and 5:00 PM.
    """

    start_seconds = 8 * 60 * 60
    end_seconds = 17 * 60 * 60

    total_seconds = random.randint(
        start_seconds,
        end_seconds,
    )

    hour = total_seconds // 3600
    minute = (total_seconds % 3600) // 60
    second = total_seconds % 60

    am_pm = "am" if hour < 12 else "pm"

    display_hour = hour % 12

    if display_hour == 0:
        display_hour = 12

    return (
        f"{display_hour:02d}",
        f"{minute:02d}",
        f"{second:02d}",
        am_pm,
    )


def count_account_touchpoints(drr_df, masterlist_accounts):
    """
    Count DRR records per masterlist account per touchpoint.

    Only accounts present in the masterlist are counted.
    """

    counts = {}

    if drr_df is None or drr_df.empty:
        return counts

    account_col = find_column(
        drr_df,
        "Account Number",
        "Account No",
        "Account No.",
        "Account",
    )

    touchpoint_col = find_column(
        drr_df,
        "Touchpoint",
        "Touch Point",
    )

    if not account_col or not touchpoint_col:
        return counts

    for account, touchpoint in zip(
        drr_df[account_col],
        drr_df[touchpoint_col],
    ):

        account = normalize_account(account)

        if not account:
            continue

        # Only masterlist accounts are checked.
        if account not in masterlist_accounts:
            continue

        touchpoint = clean_value(touchpoint).upper()

        if not touchpoint:
            continue

        # Normalize singular / plural forms.
        if touchpoint in ["SKIPS", "SKIP"]:
            touchpoint = "SKIP"

        counts.setdefault(account, {})

        counts[account][touchpoint] = (
            counts[account].get(touchpoint, 0) + 1
        )

    return counts


def build_touchpoint_row(
    account,
    touchpoint,
    template,
    masterlist_record,
    action_date,
):
    """Build one added DAR record for a touchpoint shortfall."""

    (
        action_hour,
        action_minute,
        action_second,
        action_ampm,
    ) = random_action_time()

    if touchpoint == "EMAIL":
        contact_number = clean_value(
            masterlist_record.get("email", "")
        )

    elif touchpoint == "SKIP":
        # Skip touchpoints use the Contact Number column.
        contact_number = clean_value(
            masterlist_record.get("contact_number", "")
        )

    else:
        # Call and SMS prefer a Mobile (nn) number.
        contact_number = clean_value(
            masterlist_record.get("mobile", "")
        )

        if not contact_number:
            contact_number = format_phone_number(
                masterlist_record.get("phone", "")
            )

    return {
        "Action Date": action_date,
        "Action Time B": action_hour,
        "Action Time C": action_minute,
        "Action Time D": action_second,
        "Action Time E": action_ampm,
        "Account Number": account,
        "Agency": "SPMADRID",
        "Action Code": template["action_code"],
        "Result": template["result"],
        "Contact Number / Field Effort": contact_number,
        "Payment Date": "",
        "Payment Amount": "",
        "RFD": "",
        "Product": "AL",
        "Bucket/Level": masterlist_record.get("bucket", ""),
        "Write Up": template["write_up"],
        "Payment Status": "#N/A",
        "Remarks": "",
    }


def build_touchpoint_topup_rows(
    drr_df,
    masterlist_lookup,
    action_date,
):
    """
    Add the missing touchpoint records for every masterlist account.

    If an account has 10 calls and the requirement is 20, the full
    20 call records are added. The same applies to SMS, Email and
    Skip. Accounts already at or above the requirement get nothing.
    """

    masterlist_accounts = set(masterlist_lookup.keys())

    counts = count_account_touchpoints(
        drr_df,
        masterlist_accounts,
    )

    topup_rows = []

    for account in sorted(masterlist_accounts):

        account_counts = counts.get(account, {})

        masterlist_record = masterlist_lookup.get(
            account,
            {},
        )

        for touchpoint, required in REQUIRED_TOUCHPOINTS.items():

            existing = account_counts.get(touchpoint, 0)

            if existing >= required:
                continue

            templates = TOUCHPOINT_TEMPLATES.get(
                touchpoint,
                [],
            )

            if not templates:
                continue

            for index in range(required):

                template = templates[
                    index % len(templates)
                ]

                topup_rows.append(
                    build_touchpoint_row(
                        account,
                        touchpoint,
                        template,
                        masterlist_record,
                        action_date,
                    )
                )

    return topup_rows


# ============================================================
# DAR ROW CREATION# ============================================================
# DAR ROW CREATION
# ============================================================

def get_masterlist_record(
    masterlist_lookup,
    account,
):
    account = clean_value(account)

    if account in masterlist_lookup:
        return masterlist_lookup[account]

    account_normalized = (
        account
        .replace(".0", "")
        .strip()
    )

    return masterlist_lookup.get(
        account_normalized,
        {
            "bucket": "",
            "address": "",
            "email": "",
            "phone": "",
        },
    )


def build_dar_rows(
    drr_df,
    masterlist_lookup,
    reference_lookup,
    manpower_lookup,
    consolidated_source=False,
    selected_dar_date=None,
):
    rows = []

    status_col = find_column(
        drr_df,
        "Status",
    )

    account_col = find_column(
        drr_df,
        "Account Number",
        "Account No",
        "Account No.",
        "Account",
    )

    remark_col = find_column(
        drr_df,
        "Remark",
    )

    remark_by_col = find_column(
        drr_df,
        "Remark By",
    )

    dispo_date_col = find_column(
        drr_df,
        "DISPO DATE",
        "DRR Date",
        "Action Date",
        "Date",
    )

    dialed_number_col = find_column(
        drr_df,
        "Dialed Number",
        "Contact Number",
        "Phone Number",
        "Phone",
    )

    payment_date_col = find_column(
        drr_df,
        "PTP Date",
        "PTP Payment Date",
        "Payment Date",
        "Claim Paid Date",
        "Paid Date",
    )

    payment_amount_col = find_column(
        drr_df,
        "PTP Amount",
        "PTP Payment Amount",
        "Payment Amount",
        "Claim Paid Amount",
        "Paid Amount",
    )

    for _, record in drr_df.iterrows():

        status = ""

        if status_col:
            status = clean_value(
                record.get(status_col)
            )

        # A blank status has no touchpoint to resolve against the
        # DAR Reference, so the record is excluded entirely.
        if not status:
            continue

        account = ""

        if account_col:
            account = clean_value(
                record.get(account_col)
            )

        if not account:
            continue

        reference = lookup_reference_status(
            status,
            reference_lookup,
        )

        action = reference["action"]
        action_code = reference["action_code"]
        result = reference["result"]

        # The DAR Reference touchpoint decides whether the record
        # is written at all. EXCLUDE removes it entirely.
        if clean_value(action).upper() == "EXCLUDE":
            continue

        masterlist_record = (
            get_masterlist_record(
                masterlist_lookup,
                account,
            )
        )

        # ----------------------------------------------------
        # CONTACT / FIELD EFFORT
        # ----------------------------------------------------

        action_upper = action.upper()

        if action_upper in [
            "CALL",
            "SMS",
            "VIBER",
            "SKIPS",
        ]:

            contact_number = ""

            if dialed_number_col:

                contact_number = format_phone_number(
                    record.get(
                        dialed_number_col
                    )
                )

            # Fall back to the number kept in the database.
            if not contact_number:

                contact_number = format_phone_number(
                    masterlist_record.get(
                        "phone",
                        "",
                    )
                )

        elif "EMAIL" in action_upper:

            # Email touchpoints show the account's email address.
            contact_number = clean_value(
                masterlist_record.get(
                    "email",
                    "",
                )
            )

        elif "FIELD" in action_upper:

            # Field touchpoints show the account's address.
            contact_number = clean_value(
                masterlist_record.get(
                    "address",
                    "",
                )
            )

        else:

            contact_number = ""

        # ----------------------------------------------------
        # ACTION DATE
        # ----------------------------------------------------

        if (
            consolidated_source
            and selected_dar_date
        ):

            action_date = (
                selected_dar_date.strftime(
                    "%m/%d/%Y"
                )
            )

        else:

            if dispo_date_col:

                action_date = format_date(
                    record.get(
                        dispo_date_col
                    )
                )

            else:

                action_date = ""

        # ----------------------------------------------------
        # ----------------------------------------------------
        # ACTION TIME
        # ----------------------------------------------------

        (
            action_hour,
            action_minute,
            action_second,
            action_ampm,
        ) = parse_drr_time_parts(
            record,
            drr_df,
            dispo_date_col=dispo_date_col,
        )

        # ----------------------------------------------------
        # PAYMENT DATE
        # ----------------------------------------------------

        payment_date = ""

        if payment_date_col:

            payment_date = format_date(
                record.get(
                    payment_date_col
                )
            )

        # ----------------------------------------------------
        # PAYMENT AMOUNT
        # ----------------------------------------------------

        payment_amount = ""

        if payment_amount_col:

            raw_amount = record.get(
                payment_amount_col
            )

            # A zero, blank, or unreadable amount is left blank.
            if not is_zero_or_blank(raw_amount):

                payment_amount = format_amount(
                    raw_amount
                )

        # ----------------------------------------------------
        # WRITE UP
        # ----------------------------------------------------

        remark_by = ""

        if remark_by_col:

            remark_by = clean_value(
                record.get(
                    remark_by_col
                )
            )

        remark = ""

        if remark_col:

            remark = clean_value(
                record.get(
                    remark_col
                )
            )

        employee_code = manpower_lookup.get(
            remark_by.lower(),
            "",
        )

        if employee_code and remark:

            write_up = (
                f"{employee_code} {remark}"
            )

        elif employee_code:

            write_up = employee_code

        else:

            write_up = remark

        # ----------------------------------------------------
        # FINAL DAR ROW
        # ----------------------------------------------------

        rows.append(
            {
                "Action Date": action_date,
                "Action Time B": action_hour,
                "Action Time C": action_minute,
                "Action Time D": action_second,
                "Action Time E": action_ampm,
                "Account Number": account,
                "Agency": "SPMADRID",
                "Action Code": action_code,
                "Result": result,
                "Contact Number / Field Effort": contact_number,
                "Payment Date": payment_date,
                "Payment Amount": payment_amount,
                "RFD": "",
                "Product": "AL",
                "Bucket/Level": masterlist_record["bucket"],
                "Write Up": write_up,
                "Payment Status": "#N/A",
                "Remarks": "",
            }
        )

    return rows


# ============================================================
# ACTION SHEET
# ============================================================

def clear_action_data(ws):
    if ws.max_row <= 1:
        return

    for row in ws.iter_rows(
        min_row=2,
        max_row=ws.max_row,
    ):

        for cell in row:
            cell.value = None


def get_action_headers(ws):
    headers = {}

    for cell in ws[1]:

        value = clean_value(
            cell.value
        )

        if value:

            headers[
                normalize_column_name(value)
            ] = cell.column

    return headers


def write_action_cell(
    ws,
    headers,
    name,
    row_number,
    value,
):
    key = normalize_column_name(name)

    if key in headers:

        ws.cell(
            row=row_number,
            column=headers[key],
            value=value,
        )

        return True

    for header, column in headers.items():

        if key in header or header in key:

            ws.cell(
                row=row_number,
                column=column,
                value=value,
            )

            return True

    return False


def write_dar_rows(
    ws,
    rows,
):
    headers = get_action_headers(ws)

    for row_number, record in enumerate(
        rows,
        start=2,
    ):
        # Write every non-time field first.
        for field, value in record.items():
            if field.startswith("Action Time "):
                continue

            write_action_cell(
                ws,
                headers,
                field,
                row_number,
                value,
            )

        # Then write the time into physical columns B-E
        # so no fuzzy header match can overwrite it.
        ws.cell(row=row_number, column=2).value = clean_value(
            record.get("Action Time B", "")
        )
        ws.cell(row=row_number, column=3).value = clean_value(
            record.get("Action Time C", "")
        )
        ws.cell(row=row_number, column=4).value = clean_value(
            record.get("Action Time D", "")
        )
        ws.cell(row=row_number, column=5).value = clean_value(
            record.get("Action Time E", "")
        ).lower()

# ============================================================
# SAVE DAR
# ============================================================

def save_dar_workbook(
    workbook,
    client,
    dar_date,
):
    output_folder = (
        BASE_DIR
        / "data"
        / "reports"
        / "DAR"
        / get_client_config(client)["folder"]
        / dar_date.strftime("%Y-%m-%d")
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_folder
        / (
            f"DAR {client} "
            f"{dar_date.strftime('%Y-%m-%d')}.xlsm"
        )
    )

    workbook.save(output_path)

    return output_path


# ============================================================
# MAIN DAR PAGE
# ============================================================

def renderdar():

    # --------------------------------------------------------
    # DAR-SPECIFIC CSS
    # --------------------------------------------------------

    apply_dar_styles()

    # --------------------------------------------------------
    # DAR PAGE CONTAINER
    # --------------------------------------------------------

    st.markdown(
        '<div class="dar-page">',
        unsafe_allow_html=True,
    )

    st.title("DAR")

    # ========================================================
    # CLIENT
    # ========================================================

    clients = list(
        CLIENT_CONFIG.keys()
    )

    client = st.selectbox(
        "Client",
        clients,
        key="dar_client",
    )

    client_config = get_client_config(
        client
    )

    st.caption(
        f"Reference: "
        f"{client_config['reference']}"
    )

    # ========================================================
    # DAR DATE
    # ========================================================

    dar_date = st.date_input(
        "DAR Date",
        value=date.today(),
        key="dar_date",
    )

    # ========================================================
    # DAR REFERENCE
    # ========================================================

    dar_reference_path = (
        get_dar_reference_path(client)
    )

    if not dar_reference_path:

        st.error(
            f"DAR Reference.xlsm was not "
            f"found for {client}."
        )

        st.info(
            "Expected location: "
            f"{get_client_reference_folder(client)}"
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

        return

    st.success(
        f"DAR Reference found: "
        f"{dar_reference_path.name}"
    )

    # ========================================================
    # DRR SOURCE
    # ========================================================

    st.markdown(
        '<div class="dar-section">'
        '<b>DRR Source</b>'
        '</div>',
        unsafe_allow_html=True,
    )

    drr_source = st.radio(
        "Select DRR Source",
        [
            "Upload DRR",
            "Consolidated DRR",
        ],
        horizontal=True,
        key="dar_drr_source",
    )

    drr_df = None
    drr_is_consolidated = False

    # ========================================================
    # UPLOAD DRR
    # ========================================================

    if drr_source == "Upload DRR":

        uploaded_drr = st.file_uploader(
            "Upload DRR",
            type=[
                "csv",
                "xlsx",
                "xls",
                "xlsm",
                "parquet",
            ],
            key="dar_drr_upload",
        )

        if uploaded_drr:

            try:

                drr_df = load_uploaded_drr(
                    uploaded_drr
                )

                st.success(
                    f"DRR loaded: "
                    f"{uploaded_drr.name} "
                    f"({len(drr_df):,} records)"
                )

            except Exception as exc:

                st.error(
                    f"Unable to load DRR: {exc}"
                )

                st.markdown(
                    "</div>",
                    unsafe_allow_html=True,
                )

                return

    # ========================================================
    # CONSOLIDATED DRR
    # ========================================================

    else:

        consolidated_files = (
            load_consolidated_drr_files(
                client
            )
        )

        if not consolidated_files:

            st.warning(
                "No consolidated DRR files "
                f"were found for {client}."
            )

            st.caption(
                "Checked: "
                f"{BASE_DIR / 'data' / 'consolidated' / client_config['folder']}"
            )

            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )

            return

        file_options = {
            path.name: path
            for path in consolidated_files
        }

        selected_file_name = st.selectbox(
            "Select Consolidated DRR",
            list(file_options.keys()),
            key="dar_consolidated_file",
        )

        selected_file = file_options[
            selected_file_name
        ]

        try:

            drr_df = read_consolidated_drr(
                selected_file
            )

            drr_is_consolidated = True

            st.success(
                f"Consolidated DRR loaded: "
                f"{selected_file.name} "
                f"({len(drr_df):,} records)"
            )

        except Exception as exc:

            st.error(
                f"Unable to load consolidated DRR: {exc}"
            )

            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )

            return

    if drr_df is None:

        st.info(
            "Load a DRR file to continue."
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

        return

    # ========================================================
    # MASTERLIST
    # ========================================================

    st.markdown(
        '<div class="dar-section">'
        '<b>Masterlist</b>'
        '</div>',
        unsafe_allow_html=True,
    )

    masterlist_password = st.text_input(
        "Masterlist Password (optional)",
        type="password",
        key="dar_masterlist_password",
        help=(
            "Leave blank for an unprotected workbook. "
            "If the workbook is password-protected and "
            "blank, SPM will automatically be tried."
        ),
    )

    uploaded_masterlist = st.file_uploader(
        "Upload Masterlist",
        type=[
            "xlsx",
            "xls",
            "xlsm",
        ],
        key="dar_masterlist_upload",
        help=(
            "The masterlist is associated with the "
            "selected DAR date. The date does not need "
            "to appear inside the masterlist."
        ),
    )

    masterlist_df = None
    masterlist_path = None

    # ========================================================
    # NEW MASTERLIST
    # ========================================================

    if uploaded_masterlist:

        uploaded_data = (
            uploaded_masterlist.getvalue()
        )

        try:

            with st.status(
                "Loading masterlist...",
                expanded=True,
            ) as status:

                status.write(
                    "Checking workbook..."
                )

                encrypted = is_encrypted_excel(
                    uploaded_data
                )

                if encrypted:

                    status.write(
                        "Password-protected workbook detected."
                    )

                    if masterlist_password.strip():

                        status.write(
                            "Using the password you provided..."
                        )

                    else:

                        status.write(
                            "No password entered. "
                            "Automatically trying SPM..."
                        )

                else:

                    status.write(
                        "No password protection detected."
                    )

                status.write(
                    "Reading masterlist..."
                )

                masterlist_df = (
                    read_masterlist_bytes(
                        uploaded_data,
                        uploaded_masterlist.name,
                        password=masterlist_password,
                    )
                )

                status.write(
                    "Preparing account information..."
                )

                masterlist_df = (
                    prepare_masterlist(
                        masterlist_df
                    )
                )

                status.write(
                    "Saving masterlist..."
                )

                (
                    masterlist_path,
                    masterlist_df,
                ) = save_uploaded_masterlist(
                    client,
                    dar_date,
                    uploaded_masterlist.name,
                    uploaded_data,
                    password=masterlist_password,
                )

                status.update(
                    label="Masterlist loaded successfully",
                    state="complete",
                    expanded=False,
                )

        except Exception as exc:

            st.error(
                f"Unable to process masterlist: {exc}"
            )

            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )

            return

    # ========================================================
    # EXISTING MASTERLIST
    # ========================================================

    if masterlist_df is None:

        existing_masterlist = find_masterlist(
            client,
            dar_date,
        )

        if existing_masterlist:

            try:

                with st.status(
                    "Loading existing masterlist...",
                    expanded=True,
                ) as status:

                    status.write(
                        f"Opening "
                        f"{existing_masterlist.name}..."
                    )

                    masterlist_df = (
                        read_masterlist_file(
                            existing_masterlist,
                            password=masterlist_password,
                        )
                    )

                    status.write(
                        "Preparing account information..."
                    )

                    masterlist_df = (
                        prepare_masterlist(
                            masterlist_df
                        )
                    )

                    masterlist_path = (
                        existing_masterlist
                    )

                    status.update(
                        label="Masterlist loaded successfully",
                        state="complete",
                        expanded=False,
                    )

            except Exception as exc:

                st.error(
                    f"Unable to process masterlist "
                    f"'{existing_masterlist.name}': "
                    f"{exc}"
                )

                st.markdown(
                    "</div>",
                    unsafe_allow_html=True,
                )

                return

    # ========================================================
    # MASTERLIST REQUIRED
    # ========================================================

    if masterlist_df is None:

        st.warning(
            "A masterlist associated with "
            "the selected DAR date is required "
            "before generating the DAR."
        )

        st.caption(
            "Upload the masterlist above. "
            "The selected DAR date determines "
            "its association; the date does not "
            "need to appear inside the masterlist."
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

        return

    # ========================================================
    # MASTERLIST LOOKUP
    # ========================================================

    try:

        masterlist_lookup = (
            build_masterlist_lookup(
                masterlist_df
            )
        )

    except Exception as exc:

        st.error(
            f"Unable to prepare masterlist "
            f"accounts: {exc}"
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

        return

    # ========================================================
    # FILTER DRR
    # ========================================================

    if drr_is_consolidated:

        date_filtered_drr = filter_drr_by_date(
            drr_df,
            dar_date,
        )

    else:

        date_filtered_drr = drr_df.copy()

    try:

        filtered_drr = filter_drr_by_masterlist(
            date_filtered_drr,
            masterlist_df,
        )

    except Exception as exc:

        st.error(
            f"Unable to match DRR accounts against "
            f"the masterlist: {exc}"
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

        return

    excluded_records = (
        len(date_filtered_drr) - len(filtered_drr)
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    st.markdown(
        '<div class="dar-section">'
        '<b>DAR Summary</b>'
        '</div>',
        unsafe_allow_html=True,
    )

    (
        summary_col1,
        summary_col2,
        summary_col3,
    ) = st.columns(3)

    with summary_col1:

        st.metric(
            "DRR Records",
            f"{len(drr_df):,}",
        )

    with summary_col2:

        st.metric(
            "Matching DRR Records",
            f"{len(filtered_drr):,}",
        )

    with summary_col3:

        st.metric(
            "Masterlist Accounts",
            f"{len(masterlist_lookup):,}",
        )

    st.caption(
        f"{excluded_records:,} DRR record(s) were excluded "
        f"because their account numbers were not found "
        f"in the masterlist."
    )

    if (
        drr_is_consolidated
        and filtered_drr.empty
    ):

        if date_filtered_drr.empty:
            st.warning(
                f"No DRR records were found "
                f"for {dar_date.strftime('%m/%d/%Y')}."
            )
        else:
            st.warning(
                "DRR records were found for the selected date, "
                "but none of their account numbers matched "
                "the masterlist."
            )

    # ========================================================
    # GENERATE DAR
    # ========================================================

    st.markdown(
        '<div class="dar-section">'
        '<b>DAR Generation</b>'
        '</div>',
        unsafe_allow_html=True,
    )

    (
        generate_col1,
        generate_col2,
    ) = st.columns([1, 5])

    with generate_col1:

        generate_dar = st.button(
            "Generate DAR",
            key="generate_dar_button",
        )

    # ========================================================
    # GENERATION
    # ========================================================

    if generate_dar:

        status = None

        try:

            with st.status(
                "Generating DAR...",
                expanded=True,
            ) as status:

                # ------------------------------------------------
                # LOAD REFERENCE
                # ------------------------------------------------

                status.write(
                    "Loading DAR Reference..."
                )

                workbook = read_dar_reference(
                    dar_reference_path
                )

                # ------------------------------------------------
                # REFERENCE MAPPINGS
                # ------------------------------------------------

                status.write(
                    "Reading DAR Reference mappings..."
                )

                reference_df = read_reference_sheet(
                    dar_reference_path
                )

                reference_lookup = (
                    build_reference_lookup(
                        reference_df
                    )
                )

                # ------------------------------------------------
                # MANPOWER
                # ------------------------------------------------

                status.write(
                    "Reading manpower mapping..."
                )

                manpower_df = read_manpower_sheet(
                    dar_reference_path
                )

                manpower_lookup = (
                    build_manpower_lookup(
                        manpower_df
                    )
                )

                # ------------------------------------------------
                # DAR ROWS
                # ------------------------------------------------

                status.write(
                    "Preparing DAR records..."
                )

                dar_rows = build_dar_rows(
                    filtered_drr,
                    masterlist_lookup,
                    reference_lookup,
                    manpower_lookup,
                    consolidated_source=(
                        drr_is_consolidated
                    ),
                    selected_dar_date=(
                        dar_date
                    ),
                )

                # ------------------------------------------------
                # TOUCHPOINT TOP-UP
                # ------------------------------------------------

                status.write(
                    "Checking touchpoint requirements..."
                )

                topup_rows = build_touchpoint_topup_rows(
                    filtered_drr,
                    masterlist_lookup,
                    dar_date.strftime("%m/%d/%Y"),
                )

                if topup_rows:
                    dar_rows = dar_rows + topup_rows

                    status.write(
                        f"Added {len(topup_rows):,} "
                        f"touchpoint record(s)."
                    )

                # ------------------------------------------------
                # WRITE ACTION
                # ------------------------------------------------

                status.write(
                    f"Writing {len(dar_rows):,} "
                    "records to Action..."
                )

                action_ws = workbook["Action"]

                clear_action_data(
                    action_ws
                )

                write_dar_rows(
                    action_ws,
                    dar_rows,
                )

                # ------------------------------------------------
                # SAVE
                # ------------------------------------------------

                status.write(
                    "Finalizing workbook..."
                )

                output_path = save_dar_workbook(
                    workbook,
                    client,
                    dar_date,
                )

                status.update(
                    label="DAR generated successfully",
                    state="complete",
                    expanded=False,
                )

            # ----------------------------------------------------
            # DOWNLOAD
            # ----------------------------------------------------

            st.success(
                f"DAR generated successfully: "
                f"{output_path.name}"
            )

            with open(
                output_path,
                "rb",
            ) as file:

                output_bytes = file.read()

            st.download_button(
                label="Download DAR",
                data=output_bytes,
                file_name=output_path.name,
                mime=(
                    "application/vnd.ms-excel."
                    "sheet.macroEnabled.12"
                ),
                key="download_dar_button",
            )

        except Exception as exc:

            if status:

                try:

                    status.update(
                        label="DAR generation failed",
                        state="error",
                        expanded=True,
                    )

                except Exception:
                    pass

            st.error(
                f"Unable to generate DAR: {exc}"
            )

    # --------------------------------------------------------
    # CLOSE DAR PAGE CONTAINER
    # --------------------------------------------------------

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

renderDAR = renderdar
render_dar = renderdar