# ruff: noqa: E402,I001
"""Check seeded RAG knowledge chunks.

This script verifies deterministic seed chunks in PostgreSQL metadata storage.

It does not call Qdrant, call an LLM, generate embeddings, generate answers,
promise prices, promise logistics, promise quality, promise warranty, promise
returns/exchanges, or create business commitments.
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

from app.core.database import get_session_factory
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from scripts.seed_rag_knowledge_chunks import SEED_SOURCE_NAME


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
    """Return seed rows."""

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


def check_seed_rows_exist() -> bool:
    """Check canonical seed rows exist."""

    print("=" * 80)
    print("checking seed rows exist")

    rows = get_seed_rows()
    chunk_ids = {
        str(row["chunk_id"])
        for row in rows
    }

    pprint(rows)

    checks = [
        len(rows) == len(EXPECTED_CHUNK_IDS),
        chunk_ids == EXPECTED_CHUNK_IDS,
    ]

    return all(checks)


def check_seed_row_flags() -> bool:
    """Check seed row flags."""

    print("=" * 80)
    print("checking seed row flags")

    rows = get_seed_rows()

    checks = [
        all(row["collection_name"] == "kb_chunks_v1" for row in rows),
        all(row["is_active"] is True for row in rows),
        all(row["allow_answer_reference"] is True for row in rows),
        all(row["allow_commitment_reference"] is False for row in rows),
        all(row["language"] == "zh" for row in rows),
        all(row["version"] == "v1" for row in rows),
        all(row["qdrant_point_id"] is None for row in rows),
        all(row["embedding_model"] is None for row in rows),
        all(row["embedding_dimension"] is None for row in rows),
    ]

    return all(checks)


def check_retrieval_filters() -> bool:
    """Check repository retrieval filters with seed rows."""

    print("=" * 80)
    print("checking retrieval filters")

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = KnowledgeChunkRepository(session)

        quality_sku001 = repository.list_for_retrieval(
            selected_module="quality",
            matched_sku="SKU001",
            limit=50,
        )
        quality_sku999 = repository.list_for_retrieval(
            selected_module="quality",
            matched_sku="SKU999",
            limit=50,
        )
        price_rows = repository.list_for_retrieval(
            selected_module="price",
            matched_sku=None,
            limit=50,
        )
        logistics_rows = repository.list_for_retrieval(
            selected_module="logistics",
            matched_sku=None,
            limit=50,
        )

    quality_sku001_ids = {
        str(row["chunk_id"])
        for row in quality_sku001
        if row["source_name"] == SEED_SOURCE_NAME
    }
    quality_sku999_ids = {
        str(row["chunk_id"])
        for row in quality_sku999
        if row["source_name"] == SEED_SOURCE_NAME
    }
    price_ids = {
        str(row["chunk_id"])
        for row in price_rows
        if row["source_name"] == SEED_SOURCE_NAME
    }
    logistics_ids = {
        str(row["chunk_id"])
        for row in logistics_rows
        if row["source_name"] == SEED_SOURCE_NAME
    }

    pprint(
        {
            "quality_sku001": sorted(quality_sku001_ids),
            "quality_sku999": sorted(quality_sku999_ids),
            "price": sorted(price_ids),
            "logistics": sorted(logistics_ids),
        }
    )

    checks = [
        {
            "seed_general_rag_boundary",
            "seed_quality_material_6061",
            "seed_quality_anodized_surface",
            "seed_aftersale_boundary",
        }.issubset(quality_sku001_ids),
        "seed_quality_material_6061" not in quality_sku999_ids,
        "seed_quality_anodized_surface" not in quality_sku999_ids,
        "seed_general_rag_boundary" in quality_sku999_ids,
        "seed_aftersale_boundary" in quality_sku999_ids,
        "seed_price_boundary" in price_ids,
        "seed_general_rag_boundary" in price_ids,
        "seed_logistics_boundary" in logistics_ids,
        "seed_general_rag_boundary" in logistics_ids,
    ]

    return all(checks)


def check_no_forbidden_commitments() -> bool:
    """Check seeded content has no forbidden commitment fragments."""

    print("=" * 80)
    print("checking forbidden commitment fragments")

    rows = get_seed_rows()
    serialized_rows = str(rows)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized_rows:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def main() -> int:
    """Run seed checks."""

    results = [
        check_seed_rows_exist(),
        check_seed_row_flags(),
        check_retrieval_filters(),
        check_no_forbidden_commitments(),
    ]

    print("=" * 80)

    if not all(results):
        print("rag seed knowledge chunks check failed")
        return 1

    print("rag seed knowledge chunks check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())