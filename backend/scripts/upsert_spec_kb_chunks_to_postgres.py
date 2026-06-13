# ruff: noqa: E402,I001
"""Upsert Spec KB chunks to PostgreSQL knowledge_chunks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.spec_chunk_builder import (
    DEFAULT_COLLECTION_NAME,
    SpecKBChunk,
    build_spec_kb_chunks_from_excel,
)
from app.core.database import get_session_factory


SPEC_FILE: Final[Path] = (
    PROJECT_ROOT / "data/uploads/conversations/qa_pairs_raw/spec_questions.xlsx"
)
EXPECTED_COUNT: Final[int] = 23
TABLE_NAME: Final[str] = "knowledge_chunks"


def main() -> int:
    """Upsert Spec KB chunks."""

    print("=" * 80)
    print("upserting Spec KB chunks to PostgreSQL")

    errors: list[str] = []

    if not SPEC_FILE.exists():
        errors.append(f"missing spec file: {SPEC_FILE}")
        pprint({"errors": errors})
        return 1

    chunks = build_spec_kb_chunks_from_excel(spec_file=SPEC_FILE)

    if len(chunks) != EXPECTED_COUNT:
        errors.append(f"expected {EXPECTED_COUNT} chunks, got {len(chunks)}")
        pprint({"errors": errors})
        return 1

    session_factory = get_session_factory()

    with session_factory() as session:
        table_columns = get_table_columns(session=session)

        if not table_columns:
            errors.append(f"table not found or no columns: {TABLE_NAME}")
            pprint({"errors": errors})
            return 1

        upserted_count = 0

        for chunk in chunks:
            row = build_row_for_existing_schema(
                chunk=chunk,
                table_columns=table_columns,
            )
            upsert_chunk(session=session, row=row)
            upserted_count += 1

        session.commit()

        db_count = count_spec_chunks(session=session)

    result: dict[str, Any] = {
        "spec_file": str(SPEC_FILE),
        "collection_name": DEFAULT_COLLECTION_NAME,
        "built_chunk_count": len(chunks),
        "upserted_count": upserted_count,
        "db_active_count": db_count,
        "first_chunk_id": chunks[0].chunk_id if chunks else None,
        "last_chunk_id": chunks[-1].chunk_id if chunks else None,
        "errors": errors,
    }

    if db_count != EXPECTED_COUNT:
        errors.append(
            f"expected {EXPECTED_COUNT} active db chunks, got {db_count}"
        )
        result["errors"] = errors

    pprint(result)

    if errors:
        print("Spec KB PostgreSQL upsert failed")
        return 1

    print("Spec KB PostgreSQL upsert passed")
    return 0


def get_table_columns(
    *,
    session: Any,
) -> set[str]:
    """Return public table column names."""

    result = session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
            ORDER BY ordinal_position
            """
        ),
        {"table_name": TABLE_NAME},
    )

    return {str(row[0]) for row in result.fetchall()}


def build_row_for_existing_schema(
    *,
    chunk: SpecKBChunk,
    table_columns: set[str],
) -> dict[str, Any]:
    """Build insert row according to existing schema."""

    payload = chunk.to_qdrant_payload()
    metadata = {
        "qa_id": chunk.qa_id,
        "source_group_id": chunk.source_group_id,
        "primary_intent": chunk.primary_intent,
        "secondary_intents": chunk.secondary_intents,
        "intent_subtype": chunk.intent_subtype,
        "question_raw": chunk.question_raw,
        "question_normalized": chunk.question_normalized,
        "answer_raw": chunk.answer_raw,
        "answer_standard": chunk.answer_standard,
        "related_sku_ids": chunk.related_sku_ids,
        "required_fields": chunk.required_fields,
        "answer_source": chunk.answer_source,
        "handoff_required": chunk.handoff_required,
        "risk_flags": chunk.risk_flags,
        "verification_status": chunk.verification_status,
        "review_notes": chunk.review_notes,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": chunk.allow_commitment_reference,
    }

    full_row: dict[str, Any] = {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "doc_title": chunk.doc_title,
        "chunk_text": chunk.content,
        "content": chunk.content,
        "summary": chunk.summary,
        "chunk_index": chunk.source_row_index - 2,
        "content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
        "collection_name": chunk.collection_name,
        "qdrant_collection_name": chunk.collection_name,
        "module": chunk.module,
        "source_type": chunk.source_type,
        "source_name": chunk.source_name,
        "source_row_index": chunk.source_row_index,
        "source_row_id": chunk.qa_id,
        "metadata": json.dumps(metadata, ensure_ascii=False),
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "payload": json.dumps(payload, ensure_ascii=False),
        "is_active": True,
        "is_verified": payload["is_verified"],
        "risk_level": chunk.risk_level,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": chunk.allow_commitment_reference,
    }

    row = {
        key: value
        for key, value in full_row.items()
        if key in table_columns
    }

    required_existing_columns = {
        "chunk_id",
        "content_hash",
        "collection_name",
        "chunk_index",
        "is_active",
    } & table_columns

    missing_values = [
        column
        for column in required_existing_columns
        if column not in row or row[column] is None
    ]

    if missing_values:
        raise ValueError(
            f"{chunk.chunk_id}: missing required values for {missing_values}"
        )

    return row


def upsert_chunk(
    *,
    session: Any,
    row: dict[str, Any],
) -> None:
    """Upsert one chunk."""

    if "chunk_id" not in row:
        raise ValueError("knowledge_chunks table must contain chunk_id column")

    insert_columns = list(row.keys())
    column_sql = ", ".join(insert_columns)
    value_sql = ", ".join(f":{column}" for column in insert_columns)

    update_columns = [
        column
        for column in insert_columns
        if column != "chunk_id"
    ]

    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in update_columns
    )

    if not update_sql:
        raise ValueError("no columns to update")

    sql = text(
        f"""
        INSERT INTO {TABLE_NAME} ({column_sql})
        VALUES ({value_sql})
        ON CONFLICT (chunk_id)
        DO UPDATE SET {update_sql}
        """
    )

    session.execute(sql, row)


def count_spec_chunks(
    *,
    session: Any,
) -> int:
    """Count active Spec KB chunks."""

    result = session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM knowledge_chunks
            WHERE collection_name = :collection_name
              AND chunk_id LIKE 'spec_qa_spec%%'
              AND is_active = TRUE
            """
        ),
        {"collection_name": DEFAULT_COLLECTION_NAME},
    )

    value = result.scalar_one()

    return int(value)


if __name__ == "__main__":
    raise SystemExit(main())