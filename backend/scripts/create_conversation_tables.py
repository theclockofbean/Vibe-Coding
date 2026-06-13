# ruff: noqa: E402,I001
"""Create conversation tables.

This script creates conversations and conversation_messages tables,
constraints, indexes, and updated_at trigger.

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


CREATE_CONVERSATIONS_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,

    session_id VARCHAR(128) NOT NULL UNIQUE,
    source_channel VARCHAR(64) NOT NULL DEFAULT 'local_test',
    user_id VARCHAR(128),

    status VARCHAR(32) NOT NULL DEFAULT 'active',

    title VARCHAR(255),
    last_user_text TEXT,
    last_assistant_text TEXT,

    message_count INTEGER NOT NULL DEFAULT 0,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ
);
"""

CREATE_CONVERSATION_MESSAGES_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS conversation_messages (
    id BIGSERIAL PRIMARY KEY,

    conversation_id BIGINT NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,
    session_id VARCHAR(128) NOT NULL,

    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,

    source_channel VARCHAR(64) NOT NULL DEFAULT 'local_test',
    user_id VARCHAR(128),

    selected_module VARCHAR(64),
    route_status VARCHAR(64),
    parse_status VARCHAR(64),
    handler_status VARCHAR(64),
    handoff_required BOOLEAN NOT NULL DEFAULT FALSE,
    handoff_ticket_id BIGINT,
    handoff_ticket_no VARCHAR(64),

    source_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    module_payload JSONB,
    agent_payload JSONB,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_CONVERSATIONS_STATUS_CONSTRAINT_SQL: Final[str] = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_conversations_status'
    ) THEN
        ALTER TABLE conversations
        ADD CONSTRAINT chk_conversations_status
        CHECK (
            status IN (
                'active',
                'closed',
                'archived'
            )
        );
    END IF;
END $$;
"""

CREATE_CONVERSATION_MESSAGES_ROLE_CONSTRAINT_SQL: Final[str] = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_conversation_messages_role'
    ) THEN
        ALTER TABLE conversation_messages
        ADD CONSTRAINT chk_conversation_messages_role
        CHECK (
            role IN (
                'user',
                'assistant',
                'system',
                'tool'
            )
        );
    END IF;
END $$;
"""

CREATE_INDEX_SQL_STATEMENTS: Final[tuple[str, ...]] = (
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_source_channel
    ON conversations (source_channel);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_user_id
    ON conversations (user_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_status
    ON conversations (status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
    ON conversations (updated_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_last_message_at
    ON conversations (last_message_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id
    ON conversation_messages (conversation_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_session_id
    ON conversation_messages (session_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at
    ON conversation_messages (created_at);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_role
    ON conversation_messages (role);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_selected_module
    ON conversation_messages (selected_module);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_handoff_required
    ON conversation_messages (handoff_required);
    """,
)

CREATE_UPDATED_AT_FUNCTION_SQL: Final[str] = """
CREATE OR REPLACE FUNCTION set_conversations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_UPDATED_AT_TRIGGER_SQL: Final[str] = """
DROP TRIGGER IF EXISTS trg_conversations_updated_at ON conversations;

CREATE TRIGGER trg_conversations_updated_at
BEFORE UPDATE ON conversations
FOR EACH ROW
EXECUTE FUNCTION set_conversations_updated_at();
"""


def main() -> int:
    """Create conversation tables and related database objects."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(text(CREATE_CONVERSATIONS_TABLE_SQL))
            session.execute(text(CREATE_CONVERSATION_MESSAGES_TABLE_SQL))
            session.execute(text(CREATE_CONVERSATIONS_STATUS_CONSTRAINT_SQL))
            session.execute(text(CREATE_CONVERSATION_MESSAGES_ROLE_CONSTRAINT_SQL))

            for statement in CREATE_INDEX_SQL_STATEMENTS:
                session.execute(text(statement))

            session.execute(text(CREATE_UPDATED_AT_FUNCTION_SQL))
            session.execute(text(CREATE_UPDATED_AT_TRIGGER_SQL))

    print("conversation tables created or already exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())