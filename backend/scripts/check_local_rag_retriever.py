# ruff: noqa: E402,I001
"""Check local PostgreSQL-backed RAG retriever.

This script verifies LocalKnowledgeChunkRetriever using seeded PostgreSQL
knowledge_chunks metadata.

It does not call Qdrant, call an LLM, generate answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import (
    LocalKnowledgeChunkRetriever,
    NullRetriever,
    filter_retrieved_chunk_dicts,
)
from app.core.database import get_session_factory
from scripts.seed_rag_knowledge_chunks import (
    SEED_SOURCE_NAME,
    cleanup_existing_seed_rows,
    seed_chunks,
)


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


def reset_seed_rows() -> None:
    """Reset deterministic seed rows."""

    cleanup_existing_seed_rows()
    seed_chunks()


def count_seed_rows() -> int:
    """Count current seed rows."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM knowledge_chunks
                WHERE source_name = :source_name;
                """
            ),
            {
                "source_name": SEED_SOURCE_NAME,
            },
        ).scalar_one()

    return int(result)


def check_null_retriever_still_safe() -> bool:
    """Check NullRetriever remains no-op."""

    print("=" * 80)
    print("checking NullRetriever remains safe")

    retriever = NullRetriever()

    chunks = retriever.retrieve(
        query="SKU001 阳极氧化表面处理说明",
        selected_module="quality",
        matched_sku="SKU001",
        top_k=5,
    )

    pprint(chunks)

    return chunks == []


def check_local_quality_retrieval() -> bool:
    """Check quality retrieval for SKU001."""

    print("=" * 80)
    print("checking local quality retrieval")

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(
            session=session,
            score_threshold=0.01,
        )
        chunks = retriever.retrieve(
            query="SKU001 阳极氧化 表面处理 材质说明",
            selected_module="quality",
            matched_sku="SKU001",
            top_k=5,
        )

    filtered = filter_retrieved_chunk_dicts(
        chunks=chunks,
        selected_module="quality",
        score_threshold=0.01,
    )

    ids = {
        str(chunk["chunk_id"])
        for chunk in chunks
    }
    safe_ids = {
        chunk.chunk_id
        for chunk in filtered.safe_chunks
    }

    pprint(chunks)
    pprint(filtered)

    checks = [
        "seed_quality_material_6061" in ids,
        "seed_quality_anodized_surface" in ids,
        "seed_price_boundary" not in ids,
        "seed_logistics_boundary" not in ids,
        "seed_quality_material_6061" in safe_ids,
        "seed_quality_anodized_surface" in safe_ids,
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
        len(filtered.risk_reasons) == 0,
    ]

    return all(checks)


def check_local_price_retrieval() -> bool:
    """Check price retrieval boundary chunks."""

    print("=" * 80)
    print("checking local price retrieval")

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(
            session=session,
            score_threshold=0.01,
        )
        chunks = retriever.retrieve(
            query="SKU001 多少钱 报价 价格边界",
            selected_module="price",
            matched_sku="SKU001",
            top_k=5,
        )

    ids = {
        str(chunk["chunk_id"])
        for chunk in chunks
    }

    pprint(chunks)

    checks = [
        "seed_price_boundary" in ids,
        "seed_general_rag_boundary" in ids,
        "seed_quality_material_6061" not in ids,
        "seed_logistics_boundary" not in ids,
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
    ]

    return all(checks)


def check_local_logistics_retrieval() -> bool:
    """Check logistics retrieval boundary chunks."""

    print("=" * 80)
    print("checking local logistics retrieval")

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(
            session=session,
            score_threshold=0.01,
        )
        chunks = retriever.retrieve(
            query="SKU001 发货 物流 到货 时效边界",
            selected_module="logistics",
            matched_sku="SKU001",
            top_k=5,
        )

    ids = {
        str(chunk["chunk_id"])
        for chunk in chunks
    }

    pprint(chunks)

    checks = [
        "seed_logistics_boundary" in ids,
        "seed_general_rag_boundary" in ids,
        "seed_price_boundary" not in ids,
        "seed_quality_material_6061" not in ids,
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
    ]

    return all(checks)


def check_sku_scope_filtering() -> bool:
    """Check SKU-scoped quality chunks do not leak to unrelated SKU."""

    print("=" * 80)
    print("checking SKU scope filtering")

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(
            session=session,
            score_threshold=0.01,
        )
        chunks = retriever.retrieve(
            query="SKU999 阳极氧化 表面处理 材质说明",
            selected_module="quality",
            matched_sku="SKU999",
            top_k=10,
        )

    ids = {
        str(chunk["chunk_id"])
        for chunk in chunks
    }

    pprint(chunks)

    checks = [
        "seed_quality_material_6061" not in ids,
        "seed_quality_anodized_surface" not in ids,
        "seed_general_rag_boundary" in ids,
        "seed_aftersale_boundary" in ids,
    ]

    return all(checks)


def check_invalid_query_rejected() -> bool:
    """Check invalid query is rejected."""

    print("=" * 80)
    print("checking invalid query rejection")

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(session=session)

        try:
            retriever.retrieve(
                query="   ",
                selected_module="quality",
                matched_sku=None,
                top_k=5,
            )
        except ValueError:
            return True

    return False


def check_retriever_has_no_db_side_effects() -> bool:
    """Check retrieval does not mutate seed rows."""

    print("=" * 80)
    print("checking no DB side effects")

    before_count = count_seed_rows()

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(session=session)

        for _ in range(3):
            retriever.retrieve(
                query="SKU001 阳极氧化 表面处理 材质说明",
                selected_module="quality",
                matched_sku="SKU001",
                top_k=5,
            )

    after_count = count_seed_rows()

    checks = [
        before_count == 7,
        after_count == 7,
        before_count == after_count,
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check retrieved chunks do not contain forbidden commitment fragments."""

    print("=" * 80)
    print("checking forbidden commitment fragments")

    session_factory = get_session_factory()

    with session_factory() as session:
        retriever = LocalKnowledgeChunkRetriever(session=session)
        chunks = retriever.retrieve(
            query="SKU001 价格 物流 质量 售后 边界",
            selected_module="general",
            matched_sku="SKU001",
            top_k=10,
        )

    serialized = str(chunks)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def main() -> int:
    """Run local RAG retriever checks."""

    reset_seed_rows()

    results = [
        check_null_retriever_still_safe(),
        check_local_quality_retrieval(),
        check_local_price_retrieval(),
        check_local_logistics_retrieval(),
        check_sku_scope_filtering(),
        check_invalid_query_rejected(),
        check_retriever_has_no_db_side_effects(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("local rag retriever check failed")
        return 1

    print("local rag retriever check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())