from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from app.agent.rag.answer_service import build_default_answer_service
from app.agent.rag.chunk_vector_store import DEFAULT_CHUNK_COLLECTION
from app.agent.rag.qdrant_store import DEFAULT_QDRANT_URL
from app.agent.rag.retrieval_service import build_default_retrieval_service


def _ensure_qdrant_ready() -> None:
    client = QdrantClient(url=DEFAULT_QDRANT_URL)

    try:
        collections = client.get_collections()
    except Exception as exc:
        pytest.skip(f"Qdrant is not available: {exc}")

    collection_names = {item.name for item in collections.collections}
    if DEFAULT_CHUNK_COLLECTION not in collection_names:
        pytest.skip(f"Collection {DEFAULT_CHUNK_COLLECTION} does not exist")

    count_result = client.count(
        collection_name=DEFAULT_CHUNK_COLLECTION,
        exact=True,
    )
    if count_result.count <= 0:
        pytest.skip(f"Collection {DEFAULT_CHUNK_COLLECTION} is empty")


def test_retrieval_service_with_real_qdrant_returns_context():
    _ensure_qdrant_ready()

    service = build_default_retrieval_service()

    results = service.retrieve(
        query="M10球头杆长是多少",
        domain="spec",
        limit=3,
        rerank=True,
        rerank_top_k=2,
    )

    assert len(results) >= 1

    first = results[0]
    assert first["domain"] == "spec"
    assert "M10" in first["text"]
    assert "杆长" in first["text"]
    assert first.get("score") is not None
    assert first.get("original_score") is not None
    assert first.get("rerank_score") is not None
    assert first.get("rank") == 1


def test_answer_service_with_real_qdrant_returns_grounded_answer():
    _ensure_qdrant_ready()

    service = build_default_answer_service()

    result = service.answer(
        query="M10球头杆长是多少",
        domain="spec",
        limit=3,
    )

    assert result["should_answer"] is True
    assert result["confidence"] > 0
    assert result["source_count"] >= 1
    assert result["answer"].startswith("根据知识库资料：")
    assert "M10" in result["answer"]
    assert len(result["sources"]) >= 1
    assert len(result["contexts"]) >= 1
    assert result["metadata"]["answer_mode"] == "grounded_context"
