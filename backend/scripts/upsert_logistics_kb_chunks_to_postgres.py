# ruff: noqa: E402,I001
"""Upsert Logistics KB chunk metadata to PostgreSQL knowledge_chunks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import psycopg
from psycopg.types.json import Jsonb

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.logistics_chunk_builder import (
    LogisticsKBChunk,
    build_logistics_kb_chunks,
    load_logistics_qa_records,
)


ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

LOGISTICS_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "uploads"
    / "conversations"
    / "qa_pairs_raw"
    / "logistics_questions.xlsx"
)

OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "logistics"
    / "logistics_kb_postgres_upsert_result.json"
)

LOGISTICS_POINT_NAMESPACE: Final[uuid.UUID] = uuid.UUID(
    "0d54a7de-9e2c-4b72-b9f9-4e4b3e762c19"
)

EXPECTED_CHUNK_COUNT: Final[int] = 50
IDENTIFIER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*$"
)


@dataclass(frozen=True)
class ColumnInfo:
    """Database column information."""

    name: str
    data_type: str
    udt_name: str


def upsert_logistics_kb_chunks_to_postgres() -> bool:
    """Upsert Logistics KB chunks to PostgreSQL."""

    print("=" * 80)
    print("upserting Logistics KB chunks to PostgreSQL")

    load_env_file(ENV_FILE)
    os.environ["PGCLIENTENCODING"] = "UTF8"

    errors: list[str] = []

    if not LOGISTICS_FILE.exists():
        errors.append(f"logistics file not found: {LOGISTICS_FILE}")
        pprint({"errors": errors})
        return False

    records = load_logistics_qa_records(LOGISTICS_FILE)
    chunks = build_logistics_kb_chunks(records)

    if len(chunks) != EXPECTED_CHUNK_COUNT:
        errors.append(
            f"chunk count must be {EXPECTED_CHUNK_COUNT}, got {len(chunks)}"
        )

    if errors:
        pprint({"errors": errors})
        return False

    with psycopg.connect(
        host=get_required_env("DATABASE_HOST", default="127.0.0.1"),
        port=get_required_env("DATABASE_PORT", default="5432"),
        dbname=get_required_env("DATABASE_NAME"),
        user=get_required_env("DATABASE_USER"),
        password=get_required_env("DATABASE_PASSWORD"),
    ) as connection:
        columns = load_table_columns(connection)
        validate_required_columns(columns)

        upserted_count = 0

        with connection.cursor() as cursor:
            for chunk in chunks:
                row = build_row_for_chunk(chunk)
                usable_row = {
                    key: value
                    for key, value in row.items()
                    if key in columns
                }

                execute_upsert(
                    cursor=cursor,
                    table_name="knowledge_chunks",
                    row=usable_row,
                    columns=columns,
                )
                upserted_count += 1

        connection.commit()

        stored_count = count_stored_logistics_chunks(connection)

    result = {
        "source_file": str(LOGISTICS_FILE),
        "chunk_count": len(chunks),
        "upserted_count": upserted_count,
        "stored_count": stored_count,
        "expected_chunk_count": EXPECTED_CHUNK_COUNT,
        "collection_name": "logistics_kb_v1",
        "sample_chunk_id": chunks[0].chunk_id if chunks else None,
        "errors": errors,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pprint(result)

    if stored_count < EXPECTED_CHUNK_COUNT:
        print("Logistics KB PostgreSQL upsert check failed")
        return False

    print("Logistics KB PostgreSQL upsert check passed")
    return True


def build_row_for_chunk(
    chunk: LogisticsKBChunk,
) -> dict[str, object]:
    """Build candidate row for knowledge_chunks."""

    qdrant_point_id = str(
        uuid.uuid5(LOGISTICS_POINT_NAMESPACE, chunk.chunk_id)
    )
    now = datetime.now(UTC)

    metadata = {
        **chunk.metadata,
        "qa_id": chunk.qa_id,
        "source_group_id": chunk.source_group_id,
        "source_row_index": chunk.source_row_index,
        "source_type": chunk.source_type,
        "source_name": chunk.source_name,
        "module": chunk.module,
        "intent_scope": list(chunk.intent_scope),
        "sku_scope": list(chunk.sku_scope),
        "risk_flags": list(chunk.risk_flags),
        "risk_level": chunk.risk_level,
        "handoff_required": chunk.handoff_required,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": chunk.allow_commitment_reference,
        "qdrant_collection_name": chunk.qdrant_collection_name,
        "qdrant_point_id": qdrant_point_id,
    }

    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.chunk_id,
        "doc_title": chunk.summary,
        "title": chunk.summary,
        "module": chunk.module,
        "category": chunk.module,
        "source_type": chunk.source_type,
        "source_name": chunk.source_name,
        "source_row_id": chunk.qa_id,
        "source_row_index": chunk.source_row_index,
        "chunk_index": chunk.source_row_index - 2,
        "content": chunk.content,
        "content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
        "text": chunk.content,
        "summary": chunk.summary,
        "metadata": metadata,
        "extra_metadata": metadata,
        "payload": metadata,
        "risk_flags": list(chunk.risk_flags),
        "risk_level": chunk.risk_level,
        "related_sku_ids": list(chunk.sku_scope),
        "sku_scope": list(chunk.sku_scope),
        "intent_scope": list(chunk.intent_scope),
        "verification_status": chunk.verification_status,
        "is_verified": chunk.verification_status == "verified",
        "is_active": chunk.is_active,
        "handoff_required": chunk.handoff_required,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": chunk.allow_commitment_reference,
        "qdrant_collection_name": chunk.qdrant_collection_name,
        "collection_name": chunk.qdrant_collection_name,
        "qdrant_point_id": qdrant_point_id,
        "embedding_model": "BAAI/bge-m3",
        "created_at": now,
        "updated_at": now,
    }


def execute_upsert(
    *,
    cursor: Any,
    table_name: str,
    row: dict[str, object],
    columns: dict[str, ColumnInfo],
) -> None:
    """Execute one dynamic upsert."""

    if "chunk_id" not in row:
        raise RuntimeError("usable row does not contain chunk_id")

    safe_table_name = quote_identifier(table_name)
    column_names = list(row.keys())

    for column_name in column_names:
        quote_identifier(column_name)

    insert_columns = ", ".join(quote_identifier(column) for column in column_names)
    placeholders = ", ".join(["%s"] * len(column_names))

    update_columns = [
        column
        for column in column_names
        if column not in {"chunk_id", "created_at"}
    ]
    update_assignments = ", ".join(
        f"{quote_identifier(column)} = EXCLUDED.{quote_identifier(column)}"
        for column in update_columns
    )

    query = (
        f"INSERT INTO {safe_table_name} ({insert_columns}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({quote_identifier('chunk_id')}) DO UPDATE SET "
        f"{update_assignments}"
    )

    values = [
        adapt_value_for_column(row[column], columns[column])
        for column in column_names
    ]

    cursor.execute(query, values)


def adapt_value_for_column(
    value: object,
    column: ColumnInfo,
) -> object:
    """Adapt Python value to database column type."""

    data_type = column.data_type.lower()
    udt_name = column.udt_name.lower()

    if data_type in {"json", "jsonb"} or udt_name in {"json", "jsonb"}:
        return Jsonb(to_jsonable(value))

    if data_type == "ARRAY".lower():
        if isinstance(value, tuple):
            return list(value)
        return value

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, list | tuple):
        return ";".join(str(item) for item in value)

    return value


def to_jsonable(
    value: object,
) -> object:
    """Convert value to JSON-serializable object."""

    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item_value)
            for key, item_value in value.items()
        }

    if isinstance(value, list | tuple | set):
        return [to_jsonable(item) for item in value]

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def load_table_columns(
    connection: psycopg.Connection[Any],
) -> dict[str, ColumnInfo]:
    """Load knowledge_chunks columns."""

    query = """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'knowledge_chunks'
        ORDER BY ordinal_position
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    if not rows:
        raise RuntimeError("table not found or has no columns: knowledge_chunks")

    return {
        str(row[0]): ColumnInfo(
            name=str(row[0]),
            data_type=str(row[1]),
            udt_name=str(row[2]),
        )
        for row in rows
    }


def validate_required_columns(
    columns: dict[str, ColumnInfo],
) -> None:
    """Validate minimal required columns."""

    required = {"chunk_id", "content"}
    missing = sorted(required - set(columns))

    if missing:
        raise RuntimeError(f"knowledge_chunks missing required columns: {missing}")


def count_stored_logistics_chunks(
    connection: psycopg.Connection[Any],
) -> int:
    """Count stored logistics chunks."""

    query = """
        SELECT COUNT(*)
        FROM knowledge_chunks
        WHERE chunk_id LIKE 'logistics_qa_logi%'
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        return 0

    return int(row[0])


def quote_identifier(
    identifier: str,
) -> str:
    """Quote validated SQL identifier."""

    if not IDENTIFIER_PATTERN.match(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier}")

    return f'"{identifier}"'


def get_required_env(
    key: str,
    *,
    default: str | None = None,
) -> str:
    """Read required env var."""

    value = os.getenv(key, "").strip()

    if value:
        return value

    if default is not None:
        return default

    raise RuntimeError(f"missing required env var: {key}")


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


def main() -> int:
    """Run script."""

    passed = upsert_logistics_kb_chunks_to_postgres()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())