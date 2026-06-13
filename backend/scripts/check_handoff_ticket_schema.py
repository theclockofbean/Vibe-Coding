# ruff: noqa: E402,I001
"""Check handoff_tickets database schema."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory


REQUIRED_COLUMNS: Final[set[str]] = {
    "id",
    "ticket_no",
    "status",
    "priority",
    "source_channel",
    "session_id",
    "user_id",
    "user_text",
    "selected_module",
    "route_status",
    "route_confidence",
    "candidate_modules",
    "matched_signals",
    "parse_status",
    "handler_status",
    "handoff_reason",
    "answer_text",
    "source_references",
    "module_payload",
    "risk_reasons",
    "assigned_to",
    "resolution_note",
    "created_at",
    "updated_at",
    "resolved_at",
}

REQUIRED_INDEXES: Final[set[str]] = {
    "idx_handoff_tickets_status",
    "idx_handoff_tickets_selected_module",
    "idx_handoff_tickets_created_at",
    "idx_handoff_tickets_session_id",
    "idx_handoff_tickets_user_id",
}

REQUIRED_CONSTRAINTS: Final[set[str]] = {
    "chk_handoff_tickets_status",
    "chk_handoff_tickets_priority",
}

REQUIRED_TRIGGERS: Final[set[str]] = {
    "trg_handoff_tickets_updated_at",
}


def check_table_exists() -> bool:
    """Check handoff_tickets table exists."""

    session_factory = get_session_factory()

    with session_factory() as session:
        exists = session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'handoff_tickets'
                );
                """
            )
        ).scalar()

    if exists is not True:
        print("failed: handoff_tickets table does not exist")
        return False

    print("table exists: handoff_tickets")
    return True


def get_column_names() -> set[str]:
    """Return handoff_tickets column names."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'handoff_tickets'
                ORDER BY ordinal_position;
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def get_index_names() -> set[str]:
    """Return handoff_tickets index names."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'handoff_tickets';
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def get_constraint_names() -> set[str]:
    """Return handoff_tickets constraint names."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = 'handoff_tickets';
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def get_trigger_names() -> set[str]:
    """Return handoff_tickets trigger names."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT tg.tgname
                FROM pg_trigger tg
                JOIN pg_class t ON tg.tgrelid = t.oid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = 'handoff_tickets'
                  AND NOT tg.tgisinternal;
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def check_required_set(
    *,
    label: str,
    actual: set[str],
    required: set[str],
) -> bool:
    """Check required names are present."""

    print("=" * 80)
    print(label)
    pprint(sorted(actual))

    missing = required - actual

    if missing:
        print(f"failed: missing {label}:")
        pprint(sorted(missing))
        return False

    print(f"{label} check passed")
    return True


def main() -> int:
    """Run handoff_tickets schema checks."""

    results = [
        check_table_exists(),
        check_required_set(
            label="columns",
            actual=get_column_names(),
            required=REQUIRED_COLUMNS,
        ),
        check_required_set(
            label="indexes",
            actual=get_index_names(),
            required=REQUIRED_INDEXES,
        ),
        check_required_set(
            label="constraints",
            actual=get_constraint_names(),
            required=REQUIRED_CONSTRAINTS,
        ),
        check_required_set(
            label="triggers",
            actual=get_trigger_names(),
            required=REQUIRED_TRIGGERS,
        ),
    ]

    print("=" * 80)

    if not all(results):
        print("handoff ticket schema check failed")
        return 1

    print("handoff ticket schema check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())