# ruff: noqa: E402,I001
"""Create handoff_tickets table.

This script creates the manual handoff ticket table, constraints, indexes, and
updated_at trigger.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
write customer-facing commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory


CREATE_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS handoff_tickets (
    id BIGSERIAL PRIMARY KEY,

    ticket_no VARCHAR(64) NOT NULL UNIQUE,

    status VARCHAR(32) NOT NULL DEFAULT 'open',
    priority VARCHAR(32) NOT NULL DEFAULT 'normal',

    source_channel VARCHAR(64) DEFAULT 'local_test',
    session_id VARCHAR(128),
    user_id VARCHAR(128),

    user_text TEXT NOT NULL,

    selected_module VARCHAR(64),
    route_status VARCHAR(64),
    route_confidence NUMERIC(5, 4),
    candidate_modules JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_signals JSONB NOT NULL DEFAULT '[]'::jsonb,

    parse_status VARCHAR(64),
    handler_status VARCHAR(64),

    handoff_reason TEXT NOT NULL,
    answer_text TEXT,

    source_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    module_payload JSONB,
    risk_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,

    assigned_to VARCHAR(128),
    resolution_note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
"""

CREATE_STATUS_CONSTRAINT_SQL: Final[str] = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_handoff_tickets_status'
    ) THEN
        ALTER TABLE handoff_tickets
        ADD CONSTRAINT chk_handoff_tickets_status
        CHECK (
            status IN (
                'open',
                'in_progress',
                'resolved',
                'closed',
                'cancelled'
            )
        );
    END IF;
END $$;
"""

CREATE_PRIORITY_CONSTRAINT_SQL: Final[str] = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_handoff_tickets_priority'
    ) THEN
        ALTER TABLE handoff_tickets
        ADD CONSTRAINT chk_handoff_tickets_priority
        CHECK (
            priority IN (
                'low',
                'normal',
                'high',
                'urgent'
            )
        );
    END IF;
END $$;
"""

CREATE_INDEX_SQL_STATEMENTS: Final[tuple[str, ...]] = (
    """
    CREATE INDEX IF NOT EXISTS idx_handoff_tickets_status
    ON handoff_tickets (status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_handoff_tickets_selected_module
    ON handoff_tickets (selected_module);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_handoff_tickets_created_at
    ON handoff_tickets (created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_handoff_tickets_session_id
    ON handoff_tickets (session_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_handoff_tickets_user_id
    ON handoff_tickets (user_id);
    """,
)

CREATE_UPDATED_AT_FUNCTION_SQL: Final[str] = """
CREATE OR REPLACE FUNCTION set_handoff_tickets_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_UPDATED_AT_TRIGGER_SQL: Final[str] = """
DROP TRIGGER IF EXISTS trg_handoff_tickets_updated_at ON handoff_tickets;

CREATE TRIGGER trg_handoff_tickets_updated_at
BEFORE UPDATE ON handoff_tickets
FOR EACH ROW
EXECUTE FUNCTION set_handoff_tickets_updated_at();
"""


def main() -> int:
    """Create handoff_tickets table and related database objects."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(text(CREATE_TABLE_SQL))
            session.execute(text(CREATE_STATUS_CONSTRAINT_SQL))
            session.execute(text(CREATE_PRIORITY_CONSTRAINT_SQL))

            for statement in CREATE_INDEX_SQL_STATEMENTS:
                session.execute(text(statement))

            session.execute(text(CREATE_UPDATED_AT_FUNCTION_SQL))
            session.execute(text(CREATE_UPDATED_AT_TRIGGER_SQL))

    print("handoff_tickets table created or already exists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())