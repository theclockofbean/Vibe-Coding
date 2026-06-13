"""Knowledge chunk repository.

This repository manages PostgreSQL metadata for RAG chunks.

It does not call Qdrant, call an LLM, generate embeddings, generate answers,
promise prices, promise logistics, promise quality, promise warranty, promise
returns/exchanges, or create business commitments.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.rag.schemas import KnowledgeChunk


class KnowledgeChunkRepository:
    """Repository for knowledge_chunks table."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        """Initialize repository."""

        self.session = session

    def upsert_chunk(
        self,
        chunk: KnowledgeChunk,
    ) -> dict[str, Any]:
        """Insert or update one knowledge chunk by chunk_id."""

        row = self.session.execute(
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
                    allow_commitment_reference,
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
                    :allow_commitment_reference,
                    :embedding_model,
                    :embedding_dimension,
                    :qdrant_point_id,
                    :version,
                    CAST(:metadata AS JSONB)
                )
                ON CONFLICT (chunk_id)
                DO UPDATE SET
                    collection_name = EXCLUDED.collection_name,
                    source_type = EXCLUDED.source_type,
                    source_name = EXCLUDED.source_name,
                    source_uri = EXCLUDED.source_uri,
                    doc_id = EXCLUDED.doc_id,
                    doc_title = EXCLUDED.doc_title,
                    chunk_index = EXCLUDED.chunk_index,
                    module = EXCLUDED.module,
                    sku_scope = EXCLUDED.sku_scope,
                    intent_scope = EXCLUDED.intent_scope,
                    content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash,
                    summary = EXCLUDED.summary,
                    language = EXCLUDED.language,
                    risk_level = EXCLUDED.risk_level,
                    is_active = EXCLUDED.is_active,
                    is_verified = EXCLUDED.is_verified,
                    allow_answer_reference = EXCLUDED.allow_answer_reference,
                    allow_commitment_reference =
                        EXCLUDED.allow_commitment_reference,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_dimension = EXCLUDED.embedding_dimension,
                    qdrant_point_id = EXCLUDED.qdrant_point_id,
                    version = EXCLUDED.version,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING *;
                """
            ),
            _chunk_to_params(chunk),
        ).mappings().one()

        return _row_to_dict(row)

    def get_by_chunk_id(
        self,
        chunk_id: str,
    ) -> dict[str, Any] | None:
        """Get one chunk by chunk_id."""

        row = self.session.execute(
            text(
                """
                SELECT *
                FROM knowledge_chunks
                WHERE chunk_id = :chunk_id;
                """
            ),
            {
                "chunk_id": chunk_id,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        return _row_to_dict(row)

    def list_for_retrieval(
        self,
        *,
        selected_module: str | None,
        matched_sku: str | None,
        language: str = "zh",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List active chunks eligible for retrieval."""

        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        has_selected_module = selected_module is not None
        has_matched_sku = matched_sku is not None
        sku_scope_filter = (
            json.dumps([matched_sku], ensure_ascii=False)
            if matched_sku is not None
            else "[]"
        )

        rows = self.session.execute(
            text(
                """
                SELECT *
                FROM knowledge_chunks
                WHERE is_active = TRUE
                  AND allow_answer_reference = TRUE
                  AND language = :language
                  AND (
                      :has_selected_module = FALSE
                      OR module = CAST(:selected_module AS VARCHAR)
                      OR module = 'general'
                  )
                  AND (
                      :has_matched_sku = FALSE
                      OR sku_scope = '[]'::jsonb
                      OR sku_scope @> CAST(:sku_scope_filter AS JSONB)
                  )
                ORDER BY
                    is_verified DESC,
                    CASE risk_level
                        WHEN 'low' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'high' THEN 3
                        ELSE 4
                    END ASC,
                    updated_at DESC,
                    id DESC
                LIMIT :limit;
                """
            ),
            {
                "has_selected_module": has_selected_module,
                "selected_module": selected_module,
                "has_matched_sku": has_matched_sku,
                "sku_scope_filter": sku_scope_filter,
                "language": language,
                "limit": limit,
            },
        ).mappings().all()

        return [
            _row_to_dict(row)
            for row in rows
        ]

    def count_for_retrieval(
        self,
        *,
        selected_module: str | None,
        matched_sku: str | None,
        language: str = "zh",
    ) -> int:
        """Count active chunks eligible for retrieval."""

        has_selected_module = selected_module is not None
        has_matched_sku = matched_sku is not None
        sku_scope_filter = (
            json.dumps([matched_sku], ensure_ascii=False)
            if matched_sku is not None
            else "[]"
        )

        result = self.session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM knowledge_chunks
                WHERE is_active = TRUE
                  AND allow_answer_reference = TRUE
                  AND language = :language
                  AND (
                      :has_selected_module = FALSE
                      OR module = CAST(:selected_module AS VARCHAR)
                      OR module = 'general'
                  )
                  AND (
                      :has_matched_sku = FALSE
                      OR sku_scope = '[]'::jsonb
                      OR sku_scope @> CAST(:sku_scope_filter AS JSONB)
                  );
                """
            ),
            {
                "has_selected_module": has_selected_module,
                "selected_module": selected_module,
                "has_matched_sku": has_matched_sku,
                "sku_scope_filter": sku_scope_filter,
                "language": language,
            },
        ).scalar_one()

        return int(result)

    def mark_qdrant_point(
        self,
        *,
        chunk_id: str,
        collection_name: str,
        qdrant_point_id: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> dict[str, Any] | None:
        """Attach Qdrant point metadata to one chunk."""

        if embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")

        row = self.session.execute(
            text(
                """
                UPDATE knowledge_chunks
                SET
                    collection_name = :collection_name,
                    qdrant_point_id = :qdrant_point_id,
                    embedding_model = :embedding_model,
                    embedding_dimension = :embedding_dimension,
                    updated_at = NOW()
                WHERE chunk_id = :chunk_id
                RETURNING *;
                """
            ),
            {
                "chunk_id": chunk_id,
                "collection_name": collection_name,
                "qdrant_point_id": qdrant_point_id,
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        return _row_to_dict(row)

    def set_active(
        self,
        *,
        chunk_id: str,
        is_active: bool,
    ) -> dict[str, Any] | None:
        """Set chunk active status."""

        row = self.session.execute(
            text(
                """
                UPDATE knowledge_chunks
                SET
                    is_active = :is_active,
                    updated_at = NOW()
                WHERE chunk_id = :chunk_id
                RETURNING *;
                """
            ),
            {
                "chunk_id": chunk_id,
                "is_active": is_active,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        return _row_to_dict(row)


def _chunk_to_params(
    chunk: KnowledgeChunk,
) -> dict[str, Any]:
    """Convert KnowledgeChunk to SQL params."""

    return {
        "chunk_id": chunk.chunk_id,
        "collection_name": chunk.collection_name,
        "source_type": chunk.source_type,
        "source_name": chunk.source_name,
        "source_uri": chunk.source_uri,
        "doc_id": chunk.doc_id,
        "doc_title": chunk.doc_title,
        "chunk_index": chunk.chunk_index,
        "module": chunk.module,
        "sku_scope": json.dumps(chunk.sku_scope, ensure_ascii=False),
        "intent_scope": json.dumps(chunk.intent_scope, ensure_ascii=False),
        "content": chunk.content,
        "content_hash": chunk.content_hash,
        "summary": chunk.summary,
        "language": chunk.language,
        "risk_level": chunk.risk_level,
        "is_active": chunk.is_active,
        "is_verified": chunk.is_verified,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": chunk.allow_commitment_reference,
        "embedding_model": chunk.embedding_model,
        "embedding_dimension": chunk.embedding_dimension,
        "qdrant_point_id": chunk.qdrant_point_id,
        "version": chunk.version,
        "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
    }


def _row_to_dict(
    row: Any,
) -> dict[str, Any]:
    """Convert SQLAlchemy row mapping to plain dict."""

    result = {
        str(key): value
        for key, value in row.items()
    }

    result["sku_scope"] = _json_value(result.get("sku_scope"), default=[])
    result["intent_scope"] = _json_value(result.get("intent_scope"), default=[])
    result["metadata"] = _json_value(result.get("metadata"), default={})

    return result


def _json_value(
    value: object,
    *,
    default: object,
) -> object:
    """Normalize JSONB value."""

    if value is None:
        return default

    if isinstance(value, str):
        return json.loads(value)

    return value