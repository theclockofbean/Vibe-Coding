# ruff: noqa: E402,I001
"""Check SpecKBQdrantRetriever adapter."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.spec_kb_retriever import (
    SpecKBQdrantRetriever,
    SpecKBQdrantRetrieverConfig,
    SpecKBRetrievalHit,
)


TEST_QUERIES: Final[list[str]] = [
    "SKU001是什么规格？",
    "SKU001的螺纹规格是多少？",
    "M10的球头有哪些？",
    "杆长120mm有吗？",
    "这个球头能通用适配吗？",
]


def main() -> int:
    """Run adapter check."""

    print("=" * 80)
    print("checking SpecKBQdrantRetriever adapter")

    set_required_env()

    errors: list[str] = []

    config = SpecKBQdrantRetrieverConfig.from_env()
    retriever = SpecKBQdrantRetriever(config=config)

    results: list[dict[str, Any]] = []

    for query in TEST_QUERIES:
        hits = retriever.retrieve(query=query, top_k=5)

        if not hits:
            errors.append(f"{query}: no hits")
            continue

        validate_hits(query=query, hits=hits, errors=errors)
        results.append(preview_hits(query=query, hits=hits))

    result: dict[str, Any] = {
        "collection_name": config.collection_name,
        "qdrant_url": config.qdrant_url,
        "embedding_base_url": config.embedding_base_url,
        "query_count": len(TEST_QUERIES),
        "results": results,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("SpecKBQdrantRetriever adapter check failed")
        return 1

    print("SpecKBQdrantRetriever adapter check passed")
    return 0


def set_required_env() -> None:
    """Set required env vars."""

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "240"
    os.environ["SPEC_KB_COLLECTION_NAME"] = "spec_kb_v1"
    os.environ["SPEC_KB_TOP_K"] = "5"


def validate_hits(
    *,
    query: str,
    hits: list[SpecKBRetrievalHit],
    errors: list[str],
) -> None:
    """Validate hits."""

    top_hit = hits[0]
    context = top_hit.to_context()
    payload = top_hit.payload

    if not top_hit.chunk_id.startswith("spec_qa_spec"):
        errors.append(f"{query}: top chunk_id is not spec chunk")

    if context.get("collection_name") != "spec_kb_v1":
        errors.append(f"{query}: collection_name mismatch")

    if context.get("module") != "spec":
        errors.append(f"{query}: module must be spec")

    if context.get("allow_answer_reference") is not True:
        errors.append(f"{query}: allow_answer_reference must be true")

    if context.get("allow_commitment_reference") is not False:
        errors.append(f"{query}: allow_commitment_reference must be false")

    if not str(context.get("answer_standard", "")).strip():
        errors.append(f"{query}: answer_standard is empty")

    if not str(payload.get("content", "")).strip():
        errors.append(f"{query}: content is empty")


def preview_hits(
    *,
    query: str,
    hits: list[SpecKBRetrievalHit],
) -> dict[str, Any]:
    """Preview hits."""

    return {
        "query": query,
        "hit_count": len(hits),
        "top_hits": [
            {
                "score": hit.score,
                "chunk_id": hit.chunk_id,
                "qa_id": hit.payload.get("qa_id"),
                "intent_subtype": hit.payload.get("intent_subtype"),
                "question_normalized": hit.payload.get("question_normalized"),
                "answer_standard_preview": str(
                    hit.payload.get("answer_standard", "")
                )[:160],
            }
            for hit in hits[:3]
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())