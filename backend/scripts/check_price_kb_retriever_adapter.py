# ruff: noqa: E402,I001
"""Check PriceKBQdrantRetriever adapter."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import PriceKBHit, PriceKBQdrantRetriever


TEST_QUERIES: Final[tuple[str, ...]] = (
    "SKU001多少钱？",
    "能不能给最低价？",
    "批量采购有没有折扣？",
)
EXPECTED_COLLECTION_NAME: Final[str] = "price_kb_v1"


def main() -> int:
    """Run adapter check."""

    print("=" * 80)
    print("checking PriceKBQdrantRetriever adapter")

    set_required_env()

    errors: list[str] = []
    retriever = PriceKBQdrantRetriever(top_k=5)
    query_results: list[dict[str, Any]] = []

    exported_type_check = PriceKBHit(
        chunk_id="dummy",
        score=0.0,
        payload={"collection_name": EXPECTED_COLLECTION_NAME, "module": "price"},
    )

    if exported_type_check.chunk_id != "dummy":
        errors.append("PriceKBHit export check failed")

    for query in TEST_QUERIES:
        chunks = retriever.retrieve(query)
        result = validate_chunks(query=query, chunks=chunks)
        query_results.append(result)
        errors.extend(
            f"{query}: {error}"
            for error in result["errors"]
        )

    safe_result = {
        "collection_name": retriever.collection_name,
        "query_results": query_results,
        "errors": errors,
    }

    pprint(safe_result)

    if errors:
        print("PriceKBQdrantRetriever adapter check failed")
        return 1

    print("PriceKBQdrantRetriever adapter check passed")
    return 0


def set_required_env() -> None:
    """Set required env vars."""

    os.environ["QDRANT_URL"] = "http://127.0.0.1:6333"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"


def validate_chunks(
    *,
    query: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate retrieved chunks."""

    errors: list[str] = []

    if not chunks:
        errors.append("empty chunks")

    top_chunk = chunks[0] if chunks else {}

    if top_chunk:
        if top_chunk.get("collection_name") != EXPECTED_COLLECTION_NAME:
            errors.append("top chunk collection_name must be price_kb_v1")

        if top_chunk.get("module") != "price":
            errors.append("top chunk module must be price")

        if top_chunk.get("allow_answer_reference") is not True:
            errors.append("top chunk allow_answer_reference must be true")

        if top_chunk.get("allow_commitment_reference") is not False:
            errors.append("top chunk allow_commitment_reference must be false")

        if not str(top_chunk.get("content", "")).strip():
            errors.append("top chunk content is empty")

        if not str(top_chunk.get("chunk_id", "")).startswith("price_qa_price"):
            errors.append("top chunk chunk_id must start with price_qa_price")

    return {
        "query": query,
        "chunk_count": len(chunks),
        "top_chunk": safe_chunk_preview(top_chunk),
        "errors": errors,
    }


def safe_chunk_preview(
    chunk: dict[str, Any],
) -> dict[str, Any]:
    """Return safe chunk preview."""

    allowed_keys = {
        "chunk_id",
        "doc_id",
        "doc_title",
        "summary",
        "score",
        "collection_name",
        "module",
        "source_type",
        "source_name",
        "qa_id",
        "intent_subtype",
        "risk_flags",
        "risk_level",
        "allow_answer_reference",
        "allow_commitment_reference",
        "is_verified",
    }

    return {
        key: value
        for key, value in chunk.items()
        if key in allowed_keys
    }


if __name__ == "__main__":
    raise SystemExit(main())