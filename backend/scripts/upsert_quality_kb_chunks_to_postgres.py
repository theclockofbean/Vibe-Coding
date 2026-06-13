# ruff: noqa: E402,I001
"""Upsert Quality KB chunks into PostgreSQL knowledge_chunks.

This script writes only metadata and text chunks into PostgreSQL.
It does not write vectors into Qdrant.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL, Engine

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.quality_chunk_builder import (
    QualityKBChunk,
    build_quality_kb_chunks,
    load_quality_qa_records,
)


QUALITY_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "uploads"
    / "qa_pairs"
    / "quality_questions.xlsx"
)

ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

KNOWLEDGE_CHUNKS_TABLE: Final[str] = "knowledge_chunks"
DEFAULT_COLLECTION_NAME: Final[str] = "quality_kb_v1"
DEFAULT_EMBEDDING_MODEL: Final[str] = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIMENSION: Final[int] = 1024

QDRANT_POINT_NAMESPACE: Final[uuid.UUID] = uuid.UUID(
    "e41d884d-a6c5-4b38-8803-8f8ac8d675d1"
)


def upsert_quality_kb_chunks_to_postgres() -> bool:
    """Upsert Quality KB chunks into knowledge_chunks."""

    print("=" * 80)
    print("upserting quality KB chunks into PostgreSQL")

    load_env_file(ENV_FILE)

    if not QUALITY_FILE.exists():
        print(f"failed: quality_questions.xlsx not found: {QUALITY_FILE}")
        return False

    engine = create_database_engine()
    table = reflect_knowledge_chunks_table(engine)

    records = load_quality_qa_records(workbook_path=QUALITY_FILE)
    chunks = build_quality_kb_chunks(
        records=records,
        source_uri=str(QUALITY_FILE),
    )

    rows = [
        build_insert_row(
            chunk=chunk,
            table=table,
        )
        for chunk in chunks
    ]

    errors: list[str] = []

    if not rows:
        errors.append("no quality chunks generated")

    if "chunk_id" not in table.c:
        errors.append("knowledge_chunks.chunk_id column missing")

    if errors:
        pprint({"errors": errors})
        return False

    with engine.begin() as connection:
        for row in rows:
            statement = insert(table).values(**row)
            update_columns = build_update_columns(
                table=table,
                statement=statement,
            )
            upsert_statement = statement.on_conflict_do_update(
                index_elements=["chunk_id"],
                set_=update_columns,
            )
            connection.execute(upsert_statement)

        total_count = connection.execute(
            select(func.count()).select_from(table).where(
                table.c["module"] == "quality"
            )
        ).scalar_one()

        collection_count = connection.execute(
            select(func.count()).select_from(table).where(
                table.c["module"] == "quality",
                table.c["collection_name"] == get_quality_collection_name(),
                table.c["source_name"] == "quality_questions.xlsx",
            )
        ).scalar_one()

    result = {
        "quality_file": str(QUALITY_FILE),
        "generated_chunk_count": len(chunks),
        "upserted_row_count": len(rows),
        "quality_total_count": total_count,
        "quality_collection_count": collection_count,
        "collection_name": get_quality_collection_name(),
        "embedding_model": get_embedding_model(),
        "embedding_dimension": get_embedding_dimension(),
        "sample_row": redact_row(rows[0]) if rows else None,
    }

    pprint(result)

    if collection_count < len(rows):
        print("quality KB chunks PostgreSQL upsert check failed")
        return False

    print("quality KB chunks PostgreSQL upsert check passed")
    return True


def create_database_engine() -> Engine:
    """Create SQLAlchemy engine."""

    database_url = os.getenv("DATABASE_URL", "").strip()

    if database_url:
        return create_engine(database_url)

    database_host = os.getenv("DATABASE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    database_port_text = os.getenv("DATABASE_PORT", "5432").strip() or "5432"
    database_name = os.getenv("DATABASE_NAME", "ai_knowledge_agent").strip()
    database_user = os.getenv("DATABASE_USER", "ai_kb_app").strip()
    database_password = os.getenv("DATABASE_PASSWORD", "")

    if not database_password:
        raise RuntimeError("DATABASE_PASSWORD is missing")

    url = URL.create(
        drivername="postgresql+psycopg",
        username=database_user,
        password=database_password,
        host=database_host,
        port=int(database_port_text),
        database=database_name,
    )

    return create_engine(url)


def reflect_knowledge_chunks_table(
    engine: Engine,
) -> Table:
    """Reflect knowledge_chunks table."""

    metadata = MetaData()
    table = Table(
        KNOWLEDGE_CHUNKS_TABLE,
        metadata,
        autoload_with=engine,
    )

    required_columns = {
        "chunk_id",
        "collection_name",
        "source_type",
        "source_name",
        "source_uri",
        "doc_id",
        "doc_title",
        "chunk_index",
        "module",
        "sku_scope",
        "intent_scope",
        "content",
        "content_hash",
        "summary",
        "language",
        "risk_level",
        "is_active",
        "is_verified",
        "allow_answer_reference",
        "allow_commitment_reference",
        "embedding_model",
        "embedding_dimension",
        "qdrant_point_id",
        "version",
        "metadata",
    }

    missing = sorted(required_columns - set(table.c.keys()))

    if missing:
        raise RuntimeError(f"knowledge_chunks missing columns: {missing}")

    return table


def build_insert_row(
    *,
    chunk: QualityKBChunk,
    table: Table,
) -> dict[str, Any]:
    """Build insert row for reflected knowledge_chunks table."""

    row: dict[str, Any] = {
        "chunk_id": chunk.chunk_id,
        "collection_name": get_quality_collection_name(),
        "source_type": chunk.source_type,
        "source_name": chunk.source_name,
        "source_uri": chunk.source_uri,
        "doc_id": chunk.doc_id,
        "doc_title": chunk.doc_title,
        "chunk_index": chunk.chunk_index,
        "module": chunk.module,
        "sku_scope": chunk.sku_scope,
        "intent_scope": chunk.intent_scope,
        "content": chunk.content,
        "content_hash": chunk.content_hash,
        "summary": chunk.summary,
        "language": chunk.language,
        "risk_level": chunk.risk_level,
        "is_active": chunk.is_active,
        "is_verified": chunk.is_verified,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": False,
        "embedding_model": get_embedding_model(),
        "embedding_dimension": get_embedding_dimension(),
        "qdrant_point_id": build_qdrant_point_id(chunk.chunk_id),
        "version": "v1",
        "metadata": {
            **chunk.metadata,
            "ingestion_stage": "phase3_i_b6_postgres_upsert",
            "quality_collection": get_quality_collection_name(),
            "embedding_model": get_embedding_model(),
            "embedding_dimension": get_embedding_dimension(),
        },
    }

    return {
        column_name: value
        for column_name, value in row.items()
        if column_name in table.c
    }


def build_update_columns(
    *,
    table: Table,
    statement: Any,
) -> dict[str, Any]:
    """Build ON CONFLICT update columns."""

    excluded = statement.excluded
    update_columns: dict[str, Any] = {}

    skip_columns = {
        "id",
        "chunk_id",
        "created_at",
    }

    for column_name in table.c.keys():
        if column_name in skip_columns:
            continue

        if column_name == "updated_at":
            update_columns[column_name] = func.now()
            continue

        if column_name in excluded:
            update_columns[column_name] = excluded[column_name]

    return update_columns


def build_qdrant_point_id(
    chunk_id: str,
) -> str:
    """Build stable Qdrant point ID."""

    return str(uuid.uuid5(QDRANT_POINT_NAMESPACE, chunk_id))


def get_quality_collection_name() -> str:
    """Return quality collection name."""

    return (
        os.getenv("QDRANT_COLLECTION_QUALITY", "").strip()
        or DEFAULT_COLLECTION_NAME
    )


def get_embedding_model() -> str:
    """Return embedding model."""

    return (
        os.getenv("EMBEDDING_MODEL", "").strip()
        or DEFAULT_EMBEDDING_MODEL
    )


def get_embedding_dimension() -> int:
    """Return embedding dimension."""

    value = os.getenv("EMBEDDING_DIMENSION", "").strip()

    if value:
        return int(value)

    return DEFAULT_EMBEDDING_DIMENSION


def load_env_file(
    env_file: Path,
) -> None:
    """Load simple KEY=VALUE env file without overriding existing env."""

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def redact_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Return safe row preview."""

    allowed_keys = {
        "chunk_id",
        "collection_name",
        "source_type",
        "source_name",
        "doc_id",
        "doc_title",
        "chunk_index",
        "module",
        "sku_scope",
        "intent_scope",
        "content_hash",
        "language",
        "risk_level",
        "is_active",
        "is_verified",
        "allow_answer_reference",
        "allow_commitment_reference",
        "embedding_model",
        "embedding_dimension",
        "qdrant_point_id",
        "version",
    }

    return {
        key: value
        for key, value in row.items()
        if key in allowed_keys
    }


def main() -> int:
    """Run script."""

    try:
        passed = upsert_quality_kb_chunks_to_postgres()
    except Exception as exc:
        print(
            "quality KB chunks PostgreSQL upsert crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())