# ruff: noqa: E402,I001
"""Check QdrantRetriever.

This script verifies QdrantRetriever retrieves safe RAG evidence chunks from
Qdrant and keeps commitment references disabled.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

import sys
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
    QdrantRetriever,
    QdrantVectorStore,
    filter_retrieved_chunk_dicts,
)
from scripts.create_qdrant_collection import main as create_qdrant_collection_main
from scripts.seed_rag_knowledge_chunks import cleanup_existing_seed_rows, seed_chunks
from scripts.upsert_seed_chunks_to_qdrant import upsert_seed_chunks


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


def reset_seed_and_qdrant_points() -> None:
    """Reset seed rows and upsert points."""

    cleanup_existing_seed_rows()
    seed_chunks()

    create_result = create_qdrant_collection_main()

    if create_result != 0:
        raise RuntimeError("failed to create qdrant collection")

    upsert_seed_chunks()


def build_retriever() -> QdrantRetriever:
    """Build test retriever."""

    return QdrantRetriever(
        embedding_client=DeterministicHashEmbeddingClient(
            dimension=DEFAULT_QDRANT_VECTOR_SIZE,
        ),
        vector_store=QdrantVectorStore(
            base_url=DEFAULT_QDRANT_URL,
            timeout=5.0,
        ),
        collection_name=DEFAULT_QDRANT_COLLECTION,
        embedding_dimension=DEFAULT_QDRANT_VECTOR_SIZE,
        search_limit=50,
    )


def retrieve_ids(
    *,
    retriever: QdrantRetriever,
    query: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> tuple[set[str], list[dict[str, Any]]]:
    """Retrieve chunk ids and chunks."""

    chunks = retriever.retrieve(
        query=query,
        selected_module=selected_module,
        matched_sku=matched_sku,
        top_k=5,
    )

    ids = {
        str(chunk.get("chunk_id"))
        for chunk in chunks
    }

    return ids, chunks


def check_quality_retrieval(
    retriever: QdrantRetriever,
) -> bool:
    """Check quality retrieval."""

    print("=" * 80)
    print("checking qdrant quality retrieval")

    ids, chunks = retrieve_ids(
        retriever=retriever,
        query="SKU001 阳极氧化 表面处理 材质说明",
        selected_module="quality",
        matched_sku="SKU001",
    )

    pprint(chunks)

    checks = [
        "seed_quality_material_6061" in ids,
        "seed_quality_anodized_surface" in ids,
        "seed_price_boundary" not in ids,
        "seed_logistics_boundary" not in ids,
        all(chunk["module"] in {"quality", "general"} for chunk in chunks),
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
    ]

    filtered = filter_retrieved_chunk_dicts(
        chunks=chunks,
        selected_module="quality",
        commitment_context=False,
        score_threshold=0.01,
    )

    checks.extend(
        [
            len(filtered.safe_chunks) >= 2,
            len(filtered.to_retrieved_chunk_dicts()) >= 2,
        ]
    )

    return all(checks)


def check_price_retrieval(
    retriever: QdrantRetriever,
) -> bool:
    """Check price retrieval."""

    print("=" * 80)
    print("checking qdrant price retrieval")

    ids, chunks = retrieve_ids(
        retriever=retriever,
        query="SKU001 多少钱 报价 价格边界",
        selected_module="price",
        matched_sku="SKU001",
    )

    pprint(chunks)

    checks = [
        "seed_price_boundary" in ids,
        "seed_quality_material_6061" not in ids,
        "seed_logistics_boundary" not in ids,
        all(chunk["module"] in {"price", "general"} for chunk in chunks),
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
    ]

    return all(checks)


def check_logistics_retrieval(
    retriever: QdrantRetriever,
) -> bool:
    """Check logistics retrieval."""

    print("=" * 80)
    print("checking qdrant logistics retrieval")

    ids, chunks = retrieve_ids(
        retriever=retriever,
        query="SKU001 发货 物流 到货 时效边界",
        selected_module="logistics",
        matched_sku="SKU001",
    )

    pprint(chunks)

    checks = [
        "seed_logistics_boundary" in ids,
        "seed_price_boundary" not in ids,
        "seed_quality_material_6061" not in ids,
        all(chunk["module"] in {"logistics", "general"} for chunk in chunks),
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
    ]

    return all(checks)


def check_sku_scope_filtering(
    retriever: QdrantRetriever,
) -> bool:
    """Check SKU scope filtering."""

    print("=" * 80)
    print("checking qdrant SKU scope filtering")

    ids, chunks = retrieve_ids(
        retriever=retriever,
        query="SKU999 阳极氧化 表面处理 材质说明",
        selected_module="quality",
        matched_sku="SKU999",
    )

    pprint(chunks)

    checks = [
        "seed_quality_material_6061" not in ids,
        "seed_quality_anodized_surface" not in ids,
        "seed_general_rag_boundary" in ids,
        all(chunk["module"] in {"quality", "general"} for chunk in chunks),
        all(chunk["allow_commitment_reference"] is False for chunk in chunks),
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments(
    retriever: QdrantRetriever,
) -> bool:
    """Check no forbidden commitment fragments in retrieved chunks."""

    print("=" * 80)
    print("checking forbidden commitment fragments")

    _, chunks = retrieve_ids(
        retriever=retriever,
        query="SKU001 价格 物流 质量 售后 边界",
        selected_module=None,
        matched_sku="SKU001",
    )

    serialized = str(chunks)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def main() -> int:
    """Run QdrantRetriever checks."""

    reset_seed_and_qdrant_points()

    retriever = build_retriever()

    results = [
        check_quality_retrieval(retriever),
        check_price_retrieval(retriever),
        check_logistics_retrieval(retriever),
        check_sku_scope_filtering(retriever),
        check_no_forbidden_commitment_fragments(retriever),
    ]

    print("=" * 80)

    if not all(results):
        print("qdrant retriever check failed")
        return 1

    print("qdrant retriever check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())