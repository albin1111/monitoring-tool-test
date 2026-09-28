import streamlit as st
import polars as pl
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Consolidated data written by the consolidation step.
CONSOLIDATED_PATH = PROJECT_ROOT / "data" / "consolidated"


# ============================================================
# CAMPAIGNS
# ============================================================

CAMPAIGNS = [
    "SBC B2",
    "SBC B4",
    "SBC AL B2",
    "SBC AL B6",
    "SBC Recovery",
    "SBC AL Recovery",
    "SBC WBS",
    "SBC Geox",
    "SBC Insurance",
    "SBC Homeloan",
]


# ============================================================
# MONTHS
# ============================================================

MONTHS = {
    "January": "01",
    "February": "02",
    "March": "03",
    "April": "04",
    "May": "05",
    "June": "06",
    "July": "07",
    "August": "08",
    "September": "09",
    "October": "10",
    "November": "11",
    "December": "12",
}

MONTH_NAMES = list(MONTHS.keys())


# ============================================================
# FOLDER HELPERS
# ============================================================

ALL_CAMPAIGNS_LABEL = "All Campaigns"


def campaign_to_folder(campaign):
    return campaign.strip().replace(" ", "_")


def month_to_folder(month):
    return f"{MONTHS[month]}_{month}"


def get_campaign_folder(campaign):
    return CONSOLIDATED_PATH / campaign_to_folder(campaign)


def get_campaign_month_folder(campaign, month):
    return (
        get_campaign_folder(campaign)
        / month_to_folder(month)
    )


# ============================================================
# FILE DISCOVERY
# ============================================================

def find_parquet_files(folder):
    """Return every Parquet file under a folder."""

    if not folder.exists():
        return []

    files = [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() == ".parquet"
    ]

    files.sort(
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    return files


def pick_consolidated_file(files):
    """
    Prefer an explicit consolidated file, then the newest one.
    """

    consolidated = [
        path
        for path in files
        if "consolidated" in path.name.lower()
    ]

    if consolidated:
        return consolidated[0]

    return files[0] if files else None


# ============================================================
# LOADING
# ============================================================

@st.cache_data(show_spinner=False)
def load_parquet(file_path):
    return pl.read_parquet(file_path)


@st.cache_data(show_spinner=False)
def load_campaign_data(campaign):
    """
    Load the newest consolidated file for every month
    available under a campaign.
    """

    campaign_folder = get_campaign_folder(campaign)

    frames = []

    if not campaign_folder.exists():
        return None

    for month_folder in sorted(campaign_folder.iterdir()):

        if not month_folder.is_dir():
            continue

        files = find_parquet_files(month_folder)

        if not files:
            continue

        selected = pick_consolidated_file(files)

        if selected is None:
            continue

        try:
            frame = load_parquet(str(selected))
        except Exception:
            continue

        if frame.is_empty():
            continue

        frame = frame.with_columns(
            pl.lit(month_folder.name).alias("__period")
        )

        frames.append(frame)

    if not frames:
        return None

    # Align schemas across months before combining.
    combined = pl.concat(
        frames,
        how="diagonal_relaxed",
    )

    return combined


@st.cache_data(show_spinner=False)
def load_portfolio_data(months=None):
    """
    Load every campaign's consolidated data into one frame.

    Adds __campaign and __period so the dashboard can
    filter or group without losing the source.
    """

    frames = []

    if not CONSOLIDATED_PATH.exists():
        return None

    allowed = set(months) if months else None

    for campaign_folder in sorted(CONSOLIDATED_PATH.iterdir()):

        if not campaign_folder.is_dir():
            continue

        campaign_name = campaign_folder.name

        for month_folder in sorted(campaign_folder.iterdir()):

            if not month_folder.is_dir():
                continue

            if allowed is not None:
                folder_month = month_folder.name.split("_", 1)[-1]
                if folder_month not in allowed and month_folder.name not in allowed:
                    continue

            files = find_parquet_files(month_folder)

            selected = pick_consolidated_file(files)

            if selected is None:
                continue

            try:
                frame = load_parquet(str(selected))
            except Exception:
                continue

            if frame.is_empty():
                continue

            frame = frame.with_columns(
                pl.lit(campaign_name).alias("__campaign"),
                pl.lit(month_folder.name).alias("__period"),
            )

            frames.append(frame)

    if not frames:
        return None

    return pl.concat(
        frames,
        how="diagonal_relaxed",
    )


    return combined


# ============================================================
# COLUMN RESOLUTION
# ============================================================

def find_column(df, *names):
    """
    Find a column by exact, then partial, case-insensitive match.
    """

    normalized = {
        column.strip().lower(): column
        for column in df.columns
    }

    for name in names:

        key = name.strip().lower()

        if key in normalized:
            return normalized[key]

    for column in df.columns:

        column_key = column.strip().lower()

        for name in names:

            if name.strip().lower() in column_key:
                return column

    return None


def resolve_columns(df):
    """Return the dashboard's working columns as a mapping."""

    return {
        "status": find_column(df, "Status"),
        "date": find_column(
            df,
            "Date",
            "DISPO DATE",
            "DRR Date",
            "Action Date",
        ),
        "account": find_column(
            df,
            "Account No.",
            "Account No",
            "Account Number",
            "Account",
        ),
        "agent": find_column(
            df,
            "Remark By",
            "Agent",
            "Collector",
        ),
    }


# ============================================================
# DATA PREPARATION
# ============================================================

def prepare_data(df, columns):
    """Create normalized helper columns used by every metric."""

    result = df

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if columns["status"]:
        result = result.with_columns(
            pl.col(columns["status"])
            .cast(pl.String)
            .str.strip_chars()
            .str.to_uppercase()
            .alias("__status")
        )
    else:
        result = result.with_columns(
            pl.lit("").alias("__status")
        )

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    if columns["account"]:
        result = result.with_columns(
            pl.col(columns["account"])
            .cast(pl.String)
            .str.strip_chars()
            .alias("__account")
        )
    else:
        result = result.with_columns(
            pl.lit("").alias("__account")
        )

    # --------------------------------------------------------
    # AGENT
    # --------------------------------------------------------

    if columns["agent"]:
        cleaned_agent = (
            pl.col(columns["agent"])
            .cast(pl.String)
            .str.strip_chars()
        )

        result = result.with_columns(
            pl.when(
                cleaned_agent.is_null()
                | (cleaned_agent == "")
            )
            .then(pl.lit("Unassigned"))
            .otherwise(cleaned_agent)
            .alias("__agent")
        )
    else:
        result = result.with_columns(
            pl.lit("Unassigned").alias("__agent")
        )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_column = columns["date"]

    if date_column:

        dtype = result.schema[date_column]

        if dtype == pl.Date:

            result = result.with_columns(
                pl.col(date_column).alias("__date")
            )

        elif dtype == pl.Datetime:

            result = result.with_columns(
                pl.col(date_column)
                .dt.date()
                .alias("__date")
            )

        else:

            result = result.with_columns(
                pl.col(date_column)
                .cast(pl.String)
                .str.strip_chars()
                .str.to_date(strict=False)
                .alias("__date")
            )

    else:

        result = result.with_columns(
            pl.lit(None, dtype=pl.Date).alias("__date")
        )

    return result


# ============================================================
# METRIC HELPERS
# ============================================================

def count_unique_accounts(df):
    if df.is_empty():
        return 0

    return df.filter(
        pl.col("__account").is_not_null()
        & (pl.col("__account") != "")
    ).select(
        pl.col("__account").n_unique()
    ).item()


def status_total(df, status):
    return df.filter(
        pl.col("__status") == status
    ).height


# ============================================================
# SIDEBAR CONTROLS
# ============================================================

def render_controls():
    """Client, scope and display options, rendered on the page."""

    st.subheader("Dashboard Controls")

    row1_col1, row1_col2, row1_col3 = st.columns([1.4, 1, 1])

    with row1_col1:

        client = st.selectbox(
            "Client",
            [ALL_CAMPAIGNS_LABEL] + CAMPAIGNS,
            key="dashboard_client",
        )

    is_portfolio = client == ALL_CAMPAIGNS_LABEL

    with row1_col2:

        scope = st.selectbox(
            "Data Scope",
            [
                "All Months",
                "Single Month",
            ],
            key="dashboard_scope",
        )

    month = None

    with row1_col3:

        if scope == "Single Month":

            default_index = (
                MONTH_NAMES.index("August")
                if "August" in MONTH_NAMES
                else 0
            )

            month = st.selectbox(
                "Month",
                MONTH_NAMES,
                index=default_index,
                key="dashboard_month",
            )

        else:

            st.text_input(
                "Month",
                value="All Months",
                disabled=True,
                key="dashboard_month_placeholder",
            )

    st.caption("Optional Displays")

    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)

    with row2_col1:

        show_agent = st.checkbox(
            "Agent Breakdown",
            value=True,
            key="dashboard_show_agent",
        )

    with row2_col2:

        show_trends = st.checkbox(
            "Daily Trends",
            value=True,
            key="dashboard_show_trends",
        )

    with row2_col3:

        show_records = st.checkbox(
            "Record Explorer",
            value=False,
            key="dashboard_show_records",
        )

    with row2_col4:

        show_campaign_mix = st.checkbox(
            "Campaign Mix",
            value=is_portfolio,
            disabled=not is_portfolio,
            help="Break the overview down per campaign.",
            key="dashboard_show_campaign_mix",
        )

    return {
        "client": client,
        "is_portfolio": is_portfolio,
        "campaign": client,
        "scope": scope,
        "month": month,
        "show_agent": show_agent,
        "show_trends": show_trends,
        "show_records": show_records,
        "show_campaign_mix": show_campaign_mix,
    }


# ============================================================
# SECTION - SOURCE STATUS
# ============================================================

def render_source(campaign, scope, month):
    """Show which consolidated file feeds the dashboard."""

    if scope == "Single Month":

        folder = get_campaign_month_folder(campaign, month)

        files = find_parquet_files(folder)

        if not files:
            st.warning(
                f"No consolidated file was found for "
                f"**{campaign}** — **{month}**."
            )
            st.caption(f"Checked: `{folder}`")
            st.stop()

        selected = pick_consolidated_file(files)

        files = [selected]

    else:

        folder = get_campaign_folder(campaign)

        files = []

        if folder.exists():

            for month_folder in sorted(folder.iterdir()):

                if not month_folder.is_dir():
                    continue

                month_files = find_parquet_files(month_folder)

                selected = pick_consolidated_file(month_files)

                if selected:
                    files.append(selected)

        if not files:
            st.warning(
                f"No consolidated files were found for "
                f"**{campaign}**."
            )
            st.caption(f"Checked: `{folder}`")
            st.stop()

    with st.expander(
        f"Source Files ({len(files):,})",
        expanded=False,
    ):
        for path in files:
            size_mb = path.stat().st_size / 1024 / 1024
            st.write(
                f"📄 `{path.relative_to(CONSOLIDATED_PATH)}` "
                f"— {size_mb:.1f} MB"
            )

    return files


# ============================================================
# SECTION - OVERVIEW
# ============================================================

def render_overview(df):
    """Headline metrics for the whole selection."""

    st.subheader("Overview")

    total_records = df.height
    unique_accounts = count_unique_accounts(df)

    duplicates = max(
        total_records - unique_accounts,
        0,
    )

    new_accounts = status_total(df, "NEW")
    pullout_accounts = status_total(df, "ABORT")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Overall Records", f"{total_records:,}")
    col2.metric("Unique Accounts", f"{unique_accounts:,}")
    col3.metric("Duplicate Records", f"{duplicates:,}")
    col4.metric("Distinct Statuses", f"{df['__status'].n_unique():,}")

    st.write("")

    col1, col2, col3 = st.columns(3)

    col1.metric("NEW Records", f"{new_accounts:,}")
    col2.metric("ABORT Records", f"{pullout_accounts:,}")

    accounts_per_record = (
        unique_accounts / total_records
        if total_records
        else 0
    )

    col3.metric(
        "Accounts per Record",
        f"{accounts_per_record:.2f}",
    )


# ============================================================
# SECTION - CAMPAIGN MONITORING
# ============================================================

def render_campaign_monitoring():
    """
    One row per campaign, using each campaign's consolidated data.
    """

    st.subheader("Campaign Monitoring")

    st.caption(
        "Metrics per campaign across all months with consolidated data."
    )

    rows = []

    for campaign in CAMPAIGNS:

        campaign_df = load_campaign_data(campaign)

        if campaign_df is None or campaign_df.is_empty():

            rows.append(
                {
                    "Campaign": campaign,
                    "Periods": 0,
                    "Overall Records": 0,
                    "Unique Accounts": 0,
                    "Duplicate Records": 0,
                    "NEW": 0,
                    "ABORT": 0,
                    "Agents": 0,
                }
            )

            continue

        columns = resolve_columns(campaign_df)

        prepared = prepare_data(
            campaign_df,
            columns,
        )

        total_records = prepared.height

        unique_accounts = count_unique_accounts(prepared)

        agents = prepared.filter(
            pl.col("__agent") != "Unassigned"
        ).select(
            pl.col("__agent").n_unique()
        ).item()

        rows.append(
            {
                "Campaign": campaign,
                "Periods": prepared["__period"].n_unique(),
                "Overall Records": total_records,
                "Unique Accounts": unique_accounts,
                "Duplicate Records": max(
                    total_records - unique_accounts,
                    0,
                ),
                "NEW": status_total(prepared, "NEW"),
                "ABORT": status_total(prepared, "ABORT"),
                "Agents": agents,
            }
        )

    summary = pl.DataFrame(rows).sort(
        "Overall Records",
        descending=True,
    )

    st.dataframe(
        summary.to_pandas(),
        use_container_width=True,
        hide_index=True,
    )

    chart_rows = [
        row
        for row in rows
        if row["Overall Records"] > 0
    ]

    if chart_rows:

        chart_df = pl.DataFrame(chart_rows).sort(
            "Unique Accounts",
            descending=True,
        )

        st.bar_chart(
            chart_df.to_pandas().set_index("Campaign")[
                [
                    "Overall Records",
                    "Unique Accounts",
                ]
            ]
        )

    empty_campaigns = [
        row["Campaign"]
        for row in rows
        if row["Overall Records"] == 0
    ]

    if empty_campaigns:

        st.caption(
            "No consolidated data found for: "
            + ", ".join(empty_campaigns)
        )


# ============================================================
# SECTION - STATUS BREAKDOWN
# ============================================================

def render_status_breakdown(df):
    """Records and accounts per status."""

    st.subheader("Status Breakdown")

    breakdown = (
        df
        .filter(pl.col("__status") != "")
        .group_by("__status")
        .agg(
            pl.len().alias("Overall Records"),
            pl.col("__account")
            .filter(
                pl.col("__account").is_not_null()
                & (pl.col("__account") != "")
            )
            .n_unique()
            .alias("Unique Accounts"),
        )
        .with_columns(
            (
                pl.col("Overall Records")
                - pl.col("Unique Accounts")
            ).alias("Duplicate Records")
        )
        .sort("Overall Records", descending=True)
        .rename({"__status": "Status"})
    )

    if breakdown.is_empty():
        st.info("No statuses were found in the selected data.")
        return

    st.dataframe(
        breakdown.to_pandas(),
        use_container_width=True,
        hide_index=True,
    )

    st.bar_chart(
        breakdown.to_pandas().set_index("Status")[
            ["Overall Records", "Unique Accounts"]
        ]
    )


# ============================================================
# SECTION - AGENT BREAKDOWN
# ============================================================

def render_agent_breakdown(df):
    """Optional per-agent performance table and chart."""

    st.subheader("Agent Breakdown")

    agents = (
        df
        .group_by("__agent")
        .agg(
            pl.len().alias("Overall Records"),
            pl.col("__account")
            .filter(
                pl.col("__account").is_not_null()
                & (pl.col("__account") != "")
            )
            .n_unique()
            .alias("Unique Accounts"),
        )
        .with_columns(
            (
                pl.col("Overall Records")
                - pl.col("Unique Accounts")
            ).alias("Duplicate Records")
        )
        .sort("Overall Records", descending=True)
        .rename({"__agent": "Agent"})
    )

    if agents.is_empty():
        st.info("No agent information was found.")
        return

    st.dataframe(
        agents.to_pandas(),
        use_container_width=True,
        hide_index=True,
    )

    st.bar_chart(
        agents.to_pandas().set_index("Agent")[
            ["Overall Records", "Unique Accounts"]
        ]
    )


# ============================================================
# SECTION - DAILY TRENDS
# ============================================================

def daily_counts(df, status):
    return (
        df
        .filter(pl.col("__status") == status)
        .filter(pl.col("__date").is_not_null())
        .group_by("__date")
        .agg(pl.len().alias("Accounts"))
        .sort("__date")
        .rename({"__date": "Date"})
    )


def render_trends(df):
    """Optional endorsement and pullout trend charts."""

    st.subheader("Daily Trends")

    tab_endorsement, tab_pullout, tab_status = st.tabs(
        [
            "Endorsement (NEW)",
            "Pullout (ABORT)",
            "Status Timeline",
        ]
    )

    with tab_endorsement:

        endorsement = daily_counts(df, "NEW")

        if endorsement.is_empty():
            st.info("No NEW records were found.")
        else:
            st.line_chart(
                endorsement,
                x="Date",
                y="Accounts",
            )

    with tab_pullout:

        pullout = daily_counts(df, "ABORT")

        if pullout.is_empty():
            st.info("No ABORT records were found.")
        else:
            st.line_chart(
                pullout,
                x="Date",
                y="Accounts",
            )

    with tab_status:

        timeline = (
            df
            .filter(pl.col("__date").is_not_null())
            .group_by(["__date", "__status"])
            .agg(pl.len().alias("Accounts"))
            .sort("__date")
        )

        if timeline.is_empty():
            st.info("No dated records were found.")
        else:

            status_choice = st.selectbox(
                "Status",
                sorted(
                    timeline["__status"]
                    .unique()
                    .to_list()
                ),
                key="dashboard_timeline_status",
            )

            filtered = (
                timeline
                .filter(
                    pl.col("__status") == status_choice
                )
                .rename({"__date": "Date"})
                .select(["Date", "Accounts"])
            )

            st.line_chart(
                filtered,
                x="Date",
                y="Accounts",
            )


# ============================================================
# SECTION - RECORD EXPLORER
# ============================================================

def render_records(df):
    """Optional filtered record view."""

    st.subheader("Record Explorer")

    col1, col2, col3 = st.columns(3)

    with col1:

        statuses = sorted(
            df["__status"]
            .drop_nulls()
            .unique()
            .to_list()
        )

        status_options = ["All"] + statuses

        selected_status = st.selectbox(
            "Status",
            status_options,
            key="dashboard_record_status",
        )

    with col2:

        agents = sorted(
            df["__agent"]
            .drop_nulls()
            .unique()
            .to_list()
        )

        agent_options = ["All"] + agents

        selected_agent = st.selectbox(
            "Agent",
            agent_options,
            key="dashboard_record_agent",
        )

    with col3:

        available_dates = (
            df
            .filter(pl.col("__date").is_not_null())
            .select(pl.col("__date").min().alias("lowest"))
            .item()
        )

        highest_date = (
            df
            .filter(pl.col("__date").is_not_null())
            .select(pl.col("__date").max().alias("highest"))
            .item()
        )

        if available_dates is None or highest_date is None:
            selected_dates = None
        else:
            selected_dates = st.date_input(
                "Date Range",
                value=(available_dates, highest_date),
                min_value=available_dates,
                max_value=highest_date,
                key="dashboard_record_dates",
            )

    scoped = df

    if selected_status != "All":
        scoped = scoped.filter(
            pl.col("__status") == selected_status
        )

    if selected_agent != "All":
        scoped = scoped.filter(
            pl.col("__agent") == selected_agent
        )

    if selected_dates:

        if isinstance(selected_dates, tuple):

            if len(selected_dates) == 2:
                start_date, end_date = selected_dates
            else:
                start_date = end_date = selected_dates[0]

        else:
            start_date = end_date = selected_dates

        scoped = scoped.filter(
            pl.col("__date").is_not_null()
            & (pl.col("__date") >= start_date)
            & (pl.col("__date") <= end_date)
        )

    st.caption(
        f"{scoped.height:,} record(s) in the current selection."
    )

    display_columns = [
        column
        for column in [
            "__period",
            "__date",
            "__status",
            "__account",
            "__agent",
        ]
        if column in scoped.columns
    ]

    st.dataframe(
        scoped
        .select(display_columns)
        .head(1000)
        .to_pandas(),
        use_container_width=True,
        hide_index=True,
    )

    if scoped.height > 1000:
        st.caption(
            "Showing the first 1,000 rows of the selection."
        )


# ============================================================
# DASHBOARD
# ============================================================

def renderdashboard():

    st.title("Dashboard")

    st.caption(
        "Campaign monitoring built from consolidated data."
    )

    st.divider()

    # ========================================================
    # SECTION 1 — SCOPE
    # ========================================================

    controls = render_controls()

    campaign = controls["campaign"]
    scope = controls["scope"]
    month = controls["month"]

    st.markdown(f"## {campaign}")

    scope_label = (
        month if scope == "Single Month" else "All Months"
    )

    st.caption(f"Scope: **{scope_label}**")

    if not CONSOLIDATED_PATH.exists():

        st.error("Consolidated data folder was not found.")
        st.code(str(CONSOLIDATED_PATH.resolve()))
        return

    # ========================================================
    # SECTION 2 — SOURCE
    # ========================================================

    source_files = render_source(
        campaign,
        scope,
        month,
    )

    # ========================================================
    # SECTION 3 — LOAD
    # ========================================================

    with st.spinner("Loading consolidated data..."):

        try:

            if scope == "Single Month":
                frames = [
                    load_parquet(str(path))
                    for path in source_files
                ]
                df = pl.concat(frames, how="diagonal_relaxed")

            else:
                df = load_campaign_data(campaign)

        except Exception as error:

            st.error("Unable to read the consolidated data.")
            st.exception(error)
            return

    if df is None or df.is_empty():

        st.warning("The selected scope contains no records.")
        return

    # ========================================================
    # SECTION 4 — PREPARE
    # ========================================================

    columns = resolve_columns(df)

    missing = [
        label
        for label, key in [
            ("Status", "status"),
            ("Date", "date"),
            ("Account No.", "account"),
        ]
        if columns[key] is None
    ]

    if missing:

        st.warning(
            "Some metrics are unavailable because these "
            "columns are missing: " + ", ".join(missing)
        )

    df = prepare_data(df, columns)

    st.caption(
        f"{df.height:,} records prepared from "
        f"{len(source_files):,} file(s)."
    )

    # ========================================================
    # SECTION 5 — OVERVIEW
    # ========================================================

    render_overview(df)

    st.divider()

    # ========================================================
    # SECTION 6 — OPTIONAL DISPLAYS
    # ========================================================

    render_status_breakdown(df)

    if controls["show_agent"]:

        st.divider()
        render_agent_breakdown(df)

    if controls["show_trends"]:

        st.divider()
        render_trends(df)

    if controls["show_records"]:

        st.divider()
        render_records(df)

    st.divider()

    # ========================================================
    # SECTION 7 — ALL CAMPAIGNS
    # ========================================================

    render_campaign_monitoring()

    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(
        f"Consolidated path: {CONSOLIDATED_PATH.resolve()}"
    )
    st.caption(
        f"Records in scope: {df.height:,}"
    )


# ============================================================
# DO NOT CALL renderdashboard() HERE
# ============================================================