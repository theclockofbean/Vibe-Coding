# ruff: noqa: E402,I001
"""Create knowledge_chunks table for RAG metadata.

This script creates PostgreSQL metadata storage for RAG chunks.

It does not call an LLM, generate embeddings, call Qdrant, generate customer
answers, promise prices, promise logistics, promise quality, promise warranty,
promise returns/exchanges, or create business commitments.
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
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    chunk_id VARCHAR(128) NOT NULL UNIQUE,
    collection_name VARCHAR(128) NOT NULL DEFAULT 'kb_chunks_v1',

    source_type VARCHAR(64) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    source_uri TEXT,

    doc_id VARCHAR(128) NOT NULL,
    doc_title VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,

    module VARCHAR(32) NOT NULL,
    sku_scope JSONB NOT NULL DEFAULT '[]'::jsonb,
    intent_scope JSONB NOT NULL DEFAULT '[]'::jsonb,

    content TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL UNIQUE,
    summary TEXT,

    language VARCHAR(16) NOT NULL DEFAULT 'zh',
    risk_level VARCHAR(16) NOT NULL DEFAULT 'low',

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    allow_answer_reference BOOLEAN NOT NULL DEFAULT TRUE,
    allow_commitment_reference BOOLEAN NOT NULL DEFAULT FALSE,

    embedding_model VARCHAR(128),
    embedding_dimension INTEGER,
    qdrant_point_id VARCHAR(128),

    version VARCHAR(32) NOT NULL DEFAULT 'v1',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_knowledge_chunks_chunk_index
        CHECK (chunk_index >= 0),

    CONSTRAINT chk_knowledge_chunks_module
        CHECK (module IN ('spec', 'price', 'logistics', 'quality', 'general')),

    CONSTRAINT chk_knowledge_chunks_risk_level
        CHECK (risk_level IN ('low', 'medium', 'high')),

    CONSTRAINT chk_knowledge_chunks_content_not_blank
        CHECK (length(trim(content)) > 0),

    CONSTRAINT chk_knowledge_chunks_content_hash_sha256
        CHECK (content_hash ~ '^[0-9a-f]{64}$'),

    CONSTRAINT chk_knowledge_chunks_embedding_dimension
        CHECK (embedding_dimension IS NULL OR embedding_dimension > 0),

    CONSTRAINT chk_knowledge_chunks_commitment_requires_verified
        CHECK (
            allow_commitment_reference = FALSE
            OR is_verified = TRUE
        )
);
"""


CREATE_UPDATED_AT_FUNCTION_SQL: Final[str] = """
CREATE OR REPLACE FUNCTION set_knowledge_chunks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


CREATE_UPDATED_AT_TRIGGER_SQL: Final[str] = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_knowledge_chunks_updated_at'
    ) THEN
        CREATE TRIGGER trg_knowledge_chunks_updated_at
        BEFORE UPDATE ON knowledge_chunks
        FOR EACH ROW
        EXECUTE FUNCTION set_knowledge_chunks_updated_at();
    END IF;
END;
$$;
"""


CREATE_INDEX_SQL_LIST: Final[tuple[str, ...]] = (
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_collection_name
    ON knowledge_chunks (collection_name);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source
    ON knowledge_chunks (source_type, source_name);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_id
    ON knowledge_chunks (doc_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_module
    ON knowledge_chunks (module);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_language
    ON knowledge_chunks (language);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_risk_level
    ON knowledge_chunks (risk_level);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_active_answer
    ON knowledge_chunks (is_active, allow_answer_reference);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_verified
    ON knowledge_chunks (is_verified);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_created_at
    ON knowledge_chunks (created_at);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_updated_at
    ON knowledge_chunks (updated_at);
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_chunks_qdrant_point_id
    ON knowledge_chunks (qdrant_point_id)
    WHERE qdrant_point_id IS NOT NULL;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_sku_scope_gin
    ON knowledge_chunks USING GIN (sku_scope);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_intent_scope_gin
    ON knowledge_chunks USING GIN (intent_scope);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_metadata_gin
    ON knowledge_chunks USING GIN (metadata);
    """,
)


def create_knowledge_chunks_table() -> None:
    """Create knowledge_chunks table and indexes."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(text(CREATE_TABLE_SQL))
            session.execute(text(CREATE_UPDATED_AT_FUNCTION_SQL))
            session.execute(text(CREATE_UPDATED_AT_TRIGGER_SQL))

            for sql in CREATE_INDEX_SQL_LIST:
                session.execute(text(sql))


def main() -> int:
    """Run table creation."""

    create_knowledge_chunks_table()
    print("knowledge_chunks table creation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())