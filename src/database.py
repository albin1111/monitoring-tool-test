from pathlib import Path

import duckdb

from src.config import DATABASE_PATH


def get_connection():
    connection = duckdb.connect(
        str(DATABASE_PATH)
    )

    initialize_database(connection)

    return connection


def initialize_database(connection):
    # ---------------------------------------------------------
    # IMPORTS TABLE
    # ---------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS imports (
            import_id VARCHAR,
            original_name VARCHAR,
            stored_path VARCHAR,
            imported_at TIMESTAMP,
            row_count BIGINT,
            column_count INTEGER,
            campaign VARCHAR,
            month VARCHAR,
            file_type VARCHAR
        )
        """
    )

    # ---------------------------------------------------------
    # EXISTING DATABASE MIGRATIONS
    # ---------------------------------------------------------

    # Campaign
    connection.execute(
        """
        ALTER TABLE imports
        ADD COLUMN IF NOT EXISTS campaign VARCHAR
        """
    )

    # Month
    connection.execute(
        """
        ALTER TABLE imports
        ADD COLUMN IF NOT EXISTS month VARCHAR
        """
    )

    # File Type
    connection.execute(
        """
        ALTER TABLE imports
        ADD COLUMN IF NOT EXISTS file_type VARCHAR
        """
    )