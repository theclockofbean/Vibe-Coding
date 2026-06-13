# ruff: noqa: E402,I001
"""Upsert seeded RAG chunks to Qdrant.

This script embeds deterministic seed chunks and writes them into Qdrant.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_QDRANT_VECTOR_SIZE,
    DeterministicHashEmbeddingClient,
    QdrantVectorStore,
    validate_embedding_vector,
)
from app.core.database import get_session_factory
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from scripts.seed_rag_knowledge_chunks import SEED_SOURCE_NAME


EMBEDDING_MODEL: Final[str] = "deterministic-hash-embedding-v1"
POINT_NAMESPACE: Final[uuid.UUID] = uuid.UUID("e41d884d-a6c5-4b38-8803-8f8ac8d675d1")


def stable_point_id(
    chunk_id: str,
) -> str:
    """Return stable UUID point id for chunk_id."""

    return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def build_qdrant_payload(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Build Qdrant payload from knowledge chunk row."""

    return {
        "chunk_id": row["chunk_id"],
        "collection_name": row["collection_name"],
        "source_type": row["source_type"],
        "source_name": row["source_name"],
        "source_uri": row["source_uri"],
        "doc_id": row["doc_id"],
        "doc_title": row["doc_title"],
        "chunk_index": row["chunk_index"],
        "module": row["module"],
        "sku_scope": row["sku_scope"],
        "intent_scope": row["intent_scope"],
        "content": row["content"],
        "summary": row["summary"],
        "language": row["language"],
        "risk_level": row["risk_level"],
        "is_active": row["is_active"],
        "is_verified": row["is_verified"],
        "allow_answer_reference": row["allow_answer_reference"],
        "allow_commitment_reference": row["allow_commitment_reference"],
        "version": row["version"],
        "metadata": row["metadata"],
    }


def get_seed_rows() -> list[dict[str, Any]]:
    """Return seed rows eligible for Qdrant upsert."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = KnowledgeChunkRepository(session)

        rows = repository.list_for_retrieval(
            selected_module=None,
            matched_sku=None,
            language="zh",
            limit=100,
        )

    seed_rows = [
        row
        for row in rows
        if row["source_name"] == SEED_SOURCE_NAME
    ]

    return sorted(
        seed_rows,
        key=lambda row: str(row["chunk_id"]),
    )


def upsert_seed_chunks() -> list[dict[str, Any]]:
    """Embed and upsert seed chunks to Qdrant."""

    rows = get_seed_rows()

    if not rows:
        raise RuntimeError("no seed rows found; run seed_rag_knowledge_chunks.py first")

    embedding_client = DeterministicHashEmbeddingClient(
        dimension=DEFAULT_QDRANT_VECTOR_SIZE,
    )
    store = QdrantVectorStore(
        base_url=DEFAULT_QDRANT_URL,
        timeout=5.0,
    )

    store.assert_collection_config(
        collection_name=DEFAULT_QDRANT_COLLECTION,
        expected_vector_size=DEFAULT_QDRANT_VECTOR_SIZE,
    )

    updated_rows: list[dict[str, Any]] = []
    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)

            for row in rows:
                chunk_id = str(row["chunk_id"])
                content = str(row["content"])
                point_id = stable_point_id(chunk_id)

                vector = embedding_client.embed_query(content)
                validate_embedding_vector(
                    vector,
                    expected_dimension=DEFAULT_QDRANT_VECTOR_SIZE,
                )

                payload = build_qdrant_payload(row)

                store.upsert_point(
                    collection_name=DEFAULT_QDRANT_COLLECTION,
                    point_id=point_id,
                    vector=vector,
                    payload=payload,
                )

                updated_row = repository.mark_qdrant_point(
                    chunk_id=chunk_id,
                    collection_name=DEFAULT_QDRANT_COLLECTION,
                    qdrant_point_id=point_id,
                    embedding_model=EMBEDDING_MODEL,
                    embedding_dimension=DEFAULT_QDRANT_VECTOR_SIZE,
                )

                if updated_row is None:
                    raise RuntimeError(f"failed to mark qdrant point for {chunk_id}")

                updated_rows.append(updated_row)

    return updated_rows


def main() -> int:
    """Run seed chunk Qdrant upsert."""

    print("=" * 80)
    print("upserting seed chunks to Qdrant")

    rows = upsert_seed_chunks()

    pprint(
        [
            {
                "chunk_id": row["chunk_id"],
                "qdrant_point_id": row["qdrant_point_id"],
                "embedding_model": row["embedding_model"],
                "embedding_dimension": row["embedding_dimension"],
                "allow_commitment_reference": row["allow_commitment_reference"],
            }
            for row in rows
        ]
    )

    print(f"upserted seed chunks to qdrant: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())