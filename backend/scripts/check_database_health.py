"""Database health check script.

This script validates the current PostgreSQL schema after Alembic migrations.
It does not create, update, or delete any application data.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import check_database_connection, get_engine  # noqa: E402

EXPECTED_TABLES: Final[set[str]] = {
    "alembic_version",
    "conversation_messages",
    "conversation_sessions",
    "data_import_batches",
    "evaluation_cases",
    "evaluation_results",
    "evaluation_runs",
    "knowledge_chunks",
    "products",
}

CORE_TABLES: Final[list[str]] = [
    "data_import_batches",
    "products",
    "conversation_sessions",
    "conversation_messages",
    "knowledge_chunks",
    "evaluation_cases",
    "evaluation_runs",
    "evaluation_results",
]

EXPECTED_INDEXES: Final[set[str]] = {
    "uq_data_import_batches_active_source",
}

EXPECTED_CONSTRAINTS: Final[set[str]] = {
    "ck_data_import_batches_source_sha256_format",
}


def fetch_alembic_version(connection: Connection) -> str | None:
    """Return the current Alembic version stored in the database."""

    result = connection.execute(
        text("SELECT version_num FROM alembic_version LIMIT 1")
    ).scalar_one_or_none()

    if result is None:
        return None

    return str(result)


def fetch_index_names(connection: Connection) -> set[str]:
    """Return public schema index names."""

    rows = connection.execute(
        text(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            """
        )
    ).all()

    return {str(row[0]) for row in rows}


def fetch_constraint_names(connection: Connection) -> set[str]:
    """Return public schema constraint names."""

    rows = connection.execute(
        text(
            """
            SELECT conname
            FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
            """
        )
    ).all()

    return {str(row[0]) for row in rows}


def fetch_row_counts(connection: Connection) -> dict[str, int]:
    """Return row counts for core application tables."""

    counts: dict[str, int] = {}

    for table_name in CORE_TABLES:
        counts[table_name] = int(
            connection.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar_one()
        )

    return counts


def main() -> int:
    """Run all database health checks."""

    failures: list[str] = []

    print("database connection:")
    connection_info = check_database_connection()
    print(connection_info)

    engine = get_engine()

    with engine.connect() as connection:
        table_names = set(
            inspect(connection).get_table_names(schema="public")
        )

        print("\ntables:")
        print(sorted(table_names))

        missing_tables = EXPECTED_TABLES - table_names
        if missing_tables:
            failures.append(
                "missing tables: " + ", ".join(sorted(missing_tables))
            )

        alembic_version = fetch_alembic_version(connection)
        print("\nalembic version:")
        print(alembic_version)

        if not alembic_version:
            failures.append("missing alembic version")

        index_names = fetch_index_names(connection)
        missing_indexes = EXPECTED_INDEXES - index_names

        print("\nrequired indexes:")
        print(sorted(EXPECTED_INDEXES))

        if missing_indexes:
            failures.append(
                "missing indexes: " + ", ".join(sorted(missing_indexes))
            )

        constraint_names = fetch_constraint_names(connection)
        missing_constraints = EXPECTED_CONSTRAINTS - constraint_names

        print("\nrequired constraints:")
        print(sorted(EXPECTED_CONSTRAINTS))

        if missing_constraints:
            failures.append(
                "missing constraints: "
                + ", ".join(sorted(missing_constraints))
            )

        print("\nrow counts:")
        print(fetch_row_counts(connection))

    if failures:
        print("\nhealth check failed:")
        for failure in failures:
            print(f"- {failure}")

        return 1

    print("\nhealth check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())