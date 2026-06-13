# ruff: noqa: E402,I001
"""Check seeded Qdrant points.

This script verifies Qdrant points and PostgreSQL qdrant metadata.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_QDRANT_VECTOR_SIZE,
    QdrantVectorStore,
)
from app.core.database import get_session_factory
from scripts.seed_rag_knowledge_chunks import SEED_SOURCE_NAME
from scripts.upsert_seed_chunks_to_qdrant import EMBEDDING_MODEL


EXPECTED_CHUNK_IDS: Final[set[str]] = {
    "seed_general_rag_boundary",
    "seed_spec_parameter_boundary",
    "seed_quality_material_6061",
    "seed_quality_anodized_surface",
    "seed_price_boundary",
    "seed_logistics_boundary",
    "seed_aftersale_boundary",
}

FORBIDDEN_COMMITMENT_FRAGMENTS: Final[tuple[str, ...]] = (
    "保证最低价",
    "最低价给你",
    "一定包邮",
    "保证到货",
    "今天一定发",
    "保证不坏",
    "保证不生锈",
    "保证不掉漆",
    "保证耐用",
    "能用几年",
    "一年质保",
    "终身质保",
    "七天无理由",
    "一定能退",
    "一定能换",
    "一定赔",
    "一定补发",
    "质量很好",
    "放心用",
    "完全没问题",
)


def get_seed_rows() -> list[dict[str, Any]]:
    """Return seed rows from PostgreSQL."""

    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT *
                FROM knowledge_chunks
                WHERE source_name = :source_name
                ORDER BY chunk_id;
                """
            ),
            {
                "source_name": SEED_SOURCE_NAME,
            },
        ).mappings().all()

    return [
        {
            str(key): value
            for key, value in row.items()
        }
        for row in rows
    ]


def check_postgres_qdrant_metadata() -> tuple[bool, list[dict[str, Any]]]:
    """Check qdrant metadata in PostgreSQL."""

    print("=" * 80)
    print("checking PostgreSQL qdrant metadata")

    rows = get_seed_rows()

    pprint(
        [
            {
                "chunk_id": row["chunk_id"],
                "qdrant_point_id": row["qdrant_point_id"],
                "embedding_model": row["embedding_model"],
                "embedding_dimension": row["embedding_dimension"],
            }
            for row in rows
        ]
    )

    chunk_ids = {
        str(row["chunk_id"])
        for row in rows
    }

    checks = [
        len(rows) == len(EXPECTED_CHUNK_IDS),
        chunk_ids == EXPECTED_CHUNK_IDS,
        all(row["collection_name"] == DEFAULT_QDRANT_COLLECTION for row in rows),
        all(row["qdrant_point_id"] is not None for row in rows),
        all(row["embedding_model"] == EMBEDDING_MODEL for row in rows),
        all(row["embedding_dimension"] == DEFAULT_QDRANT_VECTOR_SIZE for row in rows),
        all(row["allow_commitment_reference"] is False for row in rows),
    ]

    return all(checks), rows


def check_qdrant_points(
    *,
    rows: list[dict[str, Any]],
) -> bool:
    """Check Qdrant points exist and payload matches PostgreSQL rows."""

    print("=" * 80)
    print("checking Qdrant points")

    point_ids = [
        str(row["qdrant_point_id"])
        for row in rows
        if row["qdrant_point_id"] is not None
    ]

    store = QdrantVectorStore(
        base_url=DEFAULT_QDRANT_URL,
        timeout=5.0,
    )

    points = store.get_points(
        collection_name=DEFAULT_QDRANT_COLLECTION,
        point_ids=point_ids,
        with_payload=True,
        with_vector=False,
    )

    pprint(points)

    payload_by_chunk_id: dict[str, dict[str, Any]] = {}

    for point in points:
        payload = point.get("payload")

        if not isinstance(payload, dict):
            continue

        chunk_id = payload.get("chunk_id")

        if isinstance(chunk_id, str):
            payload_by_chunk_id[chunk_id] = {
                str(key): value
                for key, value in payload.items()
            }

    checks = [
        len(points) == len(EXPECTED_CHUNK_IDS),
        set(payload_by_chunk_id) == EXPECTED_CHUNK_IDS,
    ]

    for row in rows:
        chunk_id = str(row["chunk_id"])
        payload = payload_by_chunk_id.get(chunk_id)

        checks.extend(
            [
                payload is not None,
                payload is not None and payload["chunk_id"] == row["chunk_id"],
                payload is not None and payload["module"] == row["module"],
                payload is not None and payload["language"] == row["language"],
                payload is not None
                and payload["allow_answer_reference"]
                == row["allow_answer_reference"],
                payload is not None
                and payload["allow_commitment_reference"]
                == row["allow_commitment_reference"],
            ]
        )

    return all(checks)


def check_no_forbidden_commitments() -> bool:
    """Check Qdrant seed payload has no forbidden commitment fragments."""

    print("=" * 80)
    print("checking forbidden commitment fragments")

    rows = get_seed_rows()
    serialized_rows = str(rows)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized_rows:
            print(f"failed: forbidden fragment detected in PostgreSQL: {fragment}")
            return False

    point_ids = [
        str(row["qdrant_point_id"])
        for row in rows
        if row["qdrant_point_id"] is not None
    ]

    store = QdrantVectorStore(
        base_url=DEFAULT_QDRANT_URL,
        timeout=5.0,
    )

    points = store.get_points(
        collection_name=DEFAULT_QDRANT_COLLECTION,
        point_ids=point_ids,
        with_payload=True,
        with_vector=False,
    )

    serialized_points = str(points)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized_points:
            print(f"failed: forbidden fragment detected in Qdrant: {fragment}")
            return False

    return True


def main() -> int:
    """Run Qdrant seed point checks."""

    postgres_ok, rows = check_postgres_qdrant_metadata()
    qdrant_ok = check_qdrant_points(rows=rows)
    forbidden_ok = check_no_forbidden_commitments()

    print("=" * 80)

    if not all([postgres_ok, qdrant_ok, forbidden_ok]):
        print("qdrant seed points check failed")
        return 1

    print("qdrant seed points check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())