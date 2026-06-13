# ruff: noqa: E402,I001
"""Check conversation database schema."""

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


REQUIRED_CONVERSATIONS_COLUMNS: Final[set[str]] = {
    "id",
    "session_id",
    "source_channel",
    "user_id",
    "status",
    "title",
    "last_user_text",
    "last_assistant_text",
    "message_count",
    "metadata",
    "created_at",
    "updated_at",
    "last_message_at",
}

REQUIRED_CONVERSATION_MESSAGES_COLUMNS: Final[set[str]] = {
    "id",
    "conversation_id",
    "session_id",
    "role",
    "content",
    "source_channel",
    "user_id",
    "selected_module",
    "route_status",
    "parse_status",
    "handler_status",
    "handoff_required",
    "handoff_ticket_id",
    "handoff_ticket_no",
    "source_references",
    "module_payload",
    "agent_payload",
    "metadata",
    "created_at",
}

REQUIRED_INDEXES: Final[set[str]] = {
    "idx_conversations_source_channel",
    "idx_conversations_user_id",
    "idx_conversations_status",
    "idx_conversations_updated_at",
    "idx_conversations_last_message_at",
    "idx_conversation_messages_conversation_id",
    "idx_conversation_messages_session_id",
    "idx_conversation_messages_created_at",
    "idx_conversation_messages_role",
    "idx_conversation_messages_selected_module",
    "idx_conversation_messages_handoff_required",
}

REQUIRED_CONSTRAINTS: Final[set[str]] = {
    "chk_conversations_status",
    "chk_conversation_messages_role",
}

REQUIRED_TRIGGERS: Final[set[str]] = {
    "trg_conversations_updated_at",
}


def table_exists(table_name: str) -> bool:
    """Check whether a public table exists."""

    session_factory = get_session_factory()

    with session_factory() as session:
        exists = session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                );
                """
            ),
            {
                "table_name": table_name,
            },
        ).scalar()

    return exists is True


def get_column_names(table_name: str) -> set[str]:
    """Return table column names."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                ORDER BY ordinal_position;
                """
            ),
            {
                "table_name": table_name,
            },
        ).all()

    return {str(row[0]) for row in rows}


def get_index_names() -> set[str]:
    """Return required conversation index names."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN (
                    'conversations',
                    'conversation_messages'
                  );
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def get_constraint_names() -> set[str]:
    """Return conversation table constraint names."""

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
                  AND t.relname IN (
                    'conversations',
                    'conversation_messages'
                  );
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def get_trigger_names() -> set[str]:
    """Return conversation trigger names."""

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
                  AND t.relname IN (
                    'conversations',
                    'conversation_messages'
                  )
                  AND NOT tg.tgisinternal;
                """
            )
        ).all()

    return {str(row[0]) for row in rows}


def check_table_exists(table_name: str) -> bool:
    """Check table existence and print result."""

    exists = table_exists(table_name)

    if not exists:
        print(f"failed: table does not exist: {table_name}")
        return False

    print(f"table exists: {table_name}")
    return True


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
    """Run conversation schema checks."""

    results = [
        check_table_exists("conversations"),
        check_table_exists("conversation_messages"),
        check_required_set(
            label="conversations columns",
            actual=get_column_names("conversations"),
            required=REQUIRED_CONVERSATIONS_COLUMNS,
        ),
        check_required_set(
            label="conversation_messages columns",
            actual=get_column_names("conversation_messages"),
            required=REQUIRED_CONVERSATION_MESSAGES_COLUMNS,
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
        print("conversation schema check failed")
        return 1

    print("conversation schema check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())