# ruff: noqa: E402,I001
"""Check knowledge_chunks schema.

This script verifies the PostgreSQL metadata table for RAG chunks.

It does not call an LLM, generate embeddings, call Qdrant, generate customer
answers, promise prices, promise logistics, promise quality, promise warranty,
promise returns/exchanges, or create business commitments.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory


EXPECTED_COLUMNS: Final[dict[str, str]] = {
    "id": "bigint",
    "chunk_id": "character varying",
    "collection_name": "character varying",
    "source_type": "character varying",
    "source_name": "character varying",
    "source_uri": "text",
    "doc_id": "character varying",
    "doc_title": "character varying",
    "chunk_index": "integer",
    "module": "character varying",
    "sku_scope": "jsonb",
    "intent_scope": "jsonb",
    "content": "text",
    "content_hash": "character",
    "summary": "text",
    "language": "character varying",
    "risk_level": "character varying",
    "is_active": "boolean",
    "is_verified": "boolean",
    "allow_answer_reference": "boolean",
    "allow_commitment_reference": "boolean",
    "embedding_model": "character varying",
    "embedding_dimension": "integer",
    "qdrant_point_id": "character varying",
    "version": "character varying",
    "metadata": "jsonb",
    "created_at": "timestamp with time zone",
    "updated_at": "timestamp with time zone",
}

EXPECTED_INDEXES: Final[set[str]] = {
    "knowledge_chunks_pkey",
    "knowledge_chunks_chunk_id_key",
    "knowledge_chunks_content_hash_key",
    "idx_knowledge_chunks_collection_name",
    "idx_knowledge_chunks_source",
    "idx_knowledge_chunks_doc_id",
    "idx_knowledge_chunks_module",
    "idx_knowledge_chunks_language",
    "idx_knowledge_chunks_risk_level",
    "idx_knowledge_chunks_active_answer",
    "idx_knowledge_chunks_verified",
    "idx_knowledge_chunks_created_at",
    "idx_knowledge_chunks_updated_at",
    "uq_knowledge_chunks_qdrant_point_id",
    "idx_knowledge_chunks_sku_scope_gin",
    "idx_knowledge_chunks_intent_scope_gin",
    "idx_knowledge_chunks_metadata_gin",
}

EXPECTED_CONSTRAINTS: Final[set[str]] = {
    "knowledge_chunks_pkey",
    "knowledge_chunks_chunk_id_key",
    "knowledge_chunks_content_hash_key",
    "chk_knowledge_chunks_chunk_index",
    "chk_knowledge_chunks_module",
    "chk_knowledge_chunks_risk_level",
    "chk_knowledge_chunks_content_not_blank",
    "chk_knowledge_chunks_content_hash_sha256",
    "chk_knowledge_chunks_embedding_dimension",
    "chk_knowledge_chunks_commitment_requires_verified",
}


def get_columns() -> dict[str, str]:
    """Return table columns."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'knowledge_chunks'
                ORDER BY ordinal_position;
                """
            )
        ).mappings().all()

    return {
        str(row["column_name"]): str(row["data_type"])
        for row in rows
    }


def get_indexes() -> set[str]:
    """Return table indexes."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'knowledge_chunks'
                ORDER BY indexname;
                """
            )
        ).mappings().all()

    return {
        str(row["indexname"])
        for row in rows
    }


def get_constraints() -> set[str]:
    """Return table constraints."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'knowledge_chunks'::regclass
                ORDER BY conname;
                """
            )
        ).mappings().all()

    return {
        str(row["conname"])
        for row in rows
    }


def cleanup_test_rows() -> None:
    """Delete schema check rows."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM knowledge_chunks
                    WHERE source_name = 'schema_check_source';
                    """
                )
            )


def make_hash(content: str) -> str:
    """Return sha256 hash."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_jsonb(value: object) -> object:
    """Normalize JSONB value from psycopg variants."""

    if isinstance(value, str):
        return json.loads(value)

    return value


def insert_valid_test_row() -> dict[str, Any]:
    """Insert and return one valid test row."""

    content = "铝合金 6061 是常见轻量化材料；具体质量承诺必须以人工确认或正式规则为准。"
    content_hash = make_hash(content)

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            row = session.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id,
                        collection_name,
                        source_type,
                        source_name,
                        source_uri,
                        doc_id,
                        doc_title,
                        chunk_index,
                        module,
                        sku_scope,
                        intent_scope,
                        content,
                        content_hash,
                        summary,
                        language,
                        risk_level,
                        is_active,
                        is_verified,
                        allow_answer_reference,
                        embedding_model,
                        embedding_dimension,
                        qdrant_point_id,
                        version,
                        metadata
                    )
                    VALUES (
                        :chunk_id,
                        :collection_name,
                        :source_type,
                        :source_name,
                        :source_uri,
                        :doc_id,
                        :doc_title,
                        :chunk_index,
                        :module,
                        CAST(:sku_scope AS JSONB),
                        CAST(:intent_scope AS JSONB),
                        :content,
                        :content_hash,
                        :summary,
                        :language,
                        :risk_level,
                        :is_active,
                        :is_verified,
                        :allow_answer_reference,
                        :embedding_model,
                        :embedding_dimension,
                        :qdrant_point_id,
                        :version,
                        CAST(:metadata AS JSONB)
                    )
                    RETURNING *;
                    """
                ),
                {
                    "chunk_id": "schema_check_quality_chunk_001",
                    "collection_name": "kb_chunks_v1",
                    "source_type": "manual_doc",
                    "source_name": "schema_check_source",
                    "source_uri": "manual://schema-check",
                    "doc_id": "schema_check_doc",
                    "doc_title": "Schema Check Doc",
                    "chunk_index": 0,
                    "module": "quality",
                    "sku_scope": json.dumps(["SKU001"], ensure_ascii=False),
                    "intent_scope": json.dumps(
                        ["material_explanation"],
                        ensure_ascii=False,
                    ),
                    "content": content,
                    "content_hash": content_hash,
                    "summary": "铝合金材料说明，不能作为质量承诺。",
                    "language": "zh",
                    "risk_level": "medium",
                    "is_active": True,
                    "is_verified": True,
                    "allow_answer_reference": True,
                    "embedding_model": "test-embedding",
                    "embedding_dimension": 8,
                    "qdrant_point_id": "schema-check-point-001",
                    "version": "v1",
                    "metadata": json.dumps(
                        {
                            "purpose": "schema_check",
                        },
                        ensure_ascii=False,
                    ),
                },
            ).mappings().one()

    return {
        str(key): value
        for key, value in row.items()
    }


def insert_default_commitment_row() -> dict[str, Any]:
    """Insert row omitting allow_commitment_reference and return it."""

    content = "报价必须由人工或正式价格表确认，RAG 不能直接作为报价依据。"
    content_hash = make_hash(content)

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            row = session.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id,
                        source_type,
                        source_name,
                        doc_id,
                        doc_title,
                        chunk_index,
                        module,
                        content,
                        content_hash
                    )
                    VALUES (
                        :chunk_id,
                        :source_type,
                        :source_name,
                        :doc_id,
                        :doc_title,
                        :chunk_index,
                        :module,
                        :content,
                        :content_hash
                    )
                    RETURNING *;
                    """
                ),
                {
                    "chunk_id": "schema_check_price_boundary_001",
                    "source_type": "manual_doc",
                    "source_name": "schema_check_source",
                    "doc_id": "schema_check_price_doc",
                    "doc_title": "Price Boundary",
                    "chunk_index": 0,
                    "module": "price",
                    "content": content,
                    "content_hash": content_hash,
                },
            ).mappings().one()

    return {
        str(key): value
        for key, value in row.items()
    }


def expect_insert_failure(
    *,
    sql: str,
    params: dict[str, object],
) -> bool:
    """Expect an insert to fail because of constraints."""

    session_factory = get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                session.execute(text(sql), params)
    except IntegrityError:
        return True

    return False


def check_columns() -> bool:
    """Check expected columns."""

    print("=" * 80)
    print("checking columns")

    actual_columns = get_columns()
    pprint(actual_columns)

    missing_columns = set(EXPECTED_COLUMNS) - set(actual_columns)

    if missing_columns:
        print("failed: missing columns")
        pprint(sorted(missing_columns))
        return False

    type_mismatches = {
        column_name: {
            "expected": expected_type,
            "actual": actual_columns.get(column_name),
        }
        for column_name, expected_type in EXPECTED_COLUMNS.items()
        if actual_columns.get(column_name) != expected_type
    }

    if type_mismatches:
        print("failed: column type mismatches")
        pprint(type_mismatches)
        return False

    return True


def check_indexes() -> bool:
    """Check expected indexes."""

    print("=" * 80)
    print("checking indexes")

    actual_indexes = get_indexes()
    pprint(sorted(actual_indexes))

    missing_indexes = EXPECTED_INDEXES - actual_indexes

    if missing_indexes:
        print("failed: missing indexes")
        pprint(sorted(missing_indexes))
        return False

    return True


def check_constraints() -> bool:
    """Check expected constraints."""

    print("=" * 80)
    print("checking constraints")

    actual_constraints = get_constraints()
    pprint(sorted(actual_constraints))

    missing_constraints = EXPECTED_CONSTRAINTS - actual_constraints

    if missing_constraints:
        print("failed: missing constraints")
        pprint(sorted(missing_constraints))
        return False

    return True


def check_valid_insert_and_defaults() -> bool:
    """Check valid insert and default values."""

    print("=" * 80)
    print("checking valid insert and defaults")

    cleanup_test_rows()

    valid_row = insert_valid_test_row()
    default_row = insert_default_commitment_row()

    pprint(valid_row)
    pprint(default_row)

    valid_sku_scope = normalize_jsonb(valid_row["sku_scope"])
    valid_intent_scope = normalize_jsonb(valid_row["intent_scope"])
    valid_metadata = normalize_jsonb(valid_row["metadata"])

    default_sku_scope = normalize_jsonb(default_row["sku_scope"])
    default_intent_scope = normalize_jsonb(default_row["intent_scope"])
    default_metadata = normalize_jsonb(default_row["metadata"])

    checks = [
        valid_row["chunk_id"] == "schema_check_quality_chunk_001",
        valid_row["collection_name"] == "kb_chunks_v1",
        valid_row["module"] == "quality",
        valid_sku_scope == ["SKU001"],
        valid_intent_scope == ["material_explanation"],
        valid_metadata == {"purpose": "schema_check"},
        valid_row["allow_answer_reference"] is True,
        valid_row["allow_commitment_reference"] is False,
        valid_row["is_verified"] is True,
        valid_row["risk_level"] == "medium",
        default_row["collection_name"] == "kb_chunks_v1",
        default_row["language"] == "zh",
        default_row["risk_level"] == "low",
        default_row["is_active"] is True,
        default_row["is_verified"] is False,
        default_row["allow_answer_reference"] is True,
        default_row["allow_commitment_reference"] is False,
        default_sku_scope == [],
        default_intent_scope == [],
        default_metadata == {},
    ]

    cleanup_test_rows()

    return all(checks)


def check_constraints_reject_invalid_rows() -> bool:
    """Check invalid rows are rejected."""

    print("=" * 80)
    print("checking constraint rejection")

    invalid_module_sql = """
        INSERT INTO knowledge_chunks (
            chunk_id,
            source_type,
            source_name,
            doc_id,
            doc_title,
            chunk_index,
            module,
            content,
            content_hash
        )
        VALUES (
            :chunk_id,
            :source_type,
            :source_name,
            :doc_id,
            :doc_title,
            :chunk_index,
            :module,
            :content,
            :content_hash
        );
    """

    invalid_hash_sql = invalid_module_sql

    commitment_without_verified_sql = """
        INSERT INTO knowledge_chunks (
            chunk_id,
            source_type,
            source_name,
            doc_id,
            doc_title,
            chunk_index,
            module,
            content,
            content_hash,
            is_verified,
            allow_commitment_reference
        )
        VALUES (
            :chunk_id,
            :source_type,
            :source_name,
            :doc_id,
            :doc_title,
            :chunk_index,
            :module,
            :content,
            :content_hash,
            :is_verified,
            :allow_commitment_reference
        );
    """

    checks = [
        expect_insert_failure(
            sql=invalid_module_sql,
            params={
                "chunk_id": "schema_check_invalid_module",
                "source_type": "manual_doc",
                "source_name": "schema_check_source",
                "doc_id": "invalid_doc",
                "doc_title": "Invalid Module",
                "chunk_index": 0,
                "module": "invalid_module",
                "content": "invalid module",
                "content_hash": make_hash("invalid module"),
            },
        ),
        expect_insert_failure(
            sql=invalid_hash_sql,
            params={
                "chunk_id": "schema_check_invalid_hash",
                "source_type": "manual_doc",
                "source_name": "schema_check_source",
                "doc_id": "invalid_doc",
                "doc_title": "Invalid Hash",
                "chunk_index": 0,
                "module": "general",
                "content": "invalid hash",
                "content_hash": "not-a-sha256",
            },
        ),
        expect_insert_failure(
            sql=commitment_without_verified_sql,
            params={
                "chunk_id": "schema_check_commitment_without_verified",
                "source_type": "manual_doc",
                "source_name": "schema_check_source",
                "doc_id": "invalid_doc",
                "doc_title": "Commitment Without Verified",
                "chunk_index": 0,
                "module": "general",
                "content": "commitment without verified",
                "content_hash": make_hash("commitment without verified"),
                "is_verified": False,
                "allow_commitment_reference": True,
            },
        ),
    ]

    cleanup_test_rows()

    return all(checks)


def main() -> int:
    """Run knowledge_chunks schema checks."""

    results = [
        check_columns(),
        check_indexes(),
        check_constraints(),
        check_valid_insert_and_defaults(),
        check_constraints_reject_invalid_rows(),
    ]

    print("=" * 80)

    if not all(results):
        print("knowledge_chunks schema check failed")
        return 1

    print("knowledge_chunks schema check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())