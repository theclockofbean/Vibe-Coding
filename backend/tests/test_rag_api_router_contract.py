from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.routers import rag_api_router


class FakeEmbeddingClient:
    dimension = 8


class FakeEmbeddingService:
    client = FakeEmbeddingClient()
    vector_size = None


class FakeRetrievalService:
    embedding_service = FakeEmbeddingService()

    def retrieve(
        self,
        *,
        query,
        domain=None,
        limit=None,
        score_threshold=None,
        rerank=None,
        rerank_top_k=None,
    ):
        return [
            {
                "chunk_id": "chunk-001",
                "document_id": "doc-001",
                "domain": domain or "spec",
                "text": "M10球头，杆长60mm，适合规格查询。",
                "source": "manual-test.md",
                "source_type": "doc",
                "score": 0.36,
                "original_score": 0.36,
                "rerank_score": 0.43,
                "rank": 1,
                "rerank_reason": {"token_overlap": 1.0},
            }
        ]


class FakeAnswerService:
    def __init__(self, *, should_answer=True):
        self.should_answer = should_answer

    def answer(
        self,
        *,
        query,
        domain=None,
        limit=None,
        score_threshold=None,
        rerank=None,
        rerank_top_k=None,
    ):
        if not self.should_answer:
            return {
                "query": query,
                "domain": domain,
                "answer": "暂时没有找到可靠依据。",
                "should_answer": False,
                "confidence": 0.08,
                "source_count": 0,
                "sources": [],
                "contexts": [],
                "metadata": {
                    "answer_mode": "refusal",
                    "refusal_reason": "low_confidence",
                    "rerank": rerank,
                    "rerank_top_k": rerank_top_k,
                    "limit": limit,
                    "score_threshold": score_threshold,
                },
            }

        return {
            "query": query,
            "domain": domain,
            "answer": "根据知识库资料：M10球头，杆长60mm。",
            "should_answer": True,
            "confidence": 0.43,
            "source_count": 1,
            "sources": [
                {
                    "index": 1,
                    "chunk_id": "chunk-001",
                    "document_id": "doc-001",
                    "domain": domain or "spec",
                    "source": "manual-test.md",
                    "source_type": "doc",
                    "score": 0.36,
                    "original_score": 0.36,
                    "rerank_score": 0.43,
                    "rank": 1,
                }
            ],
            "contexts": [
                {
                    "index": 1,
                    "chunk_id": "chunk-001",
                    "document_id": "doc-001",
                    "domain": domain or "spec",
                    "text": "M10球头，杆长60mm，适合规格查询。",
                    "source": "manual-test.md",
                    "source_type": "doc",
                    "score": 0.36,
                    "original_score": 0.36,
                    "rerank_score": 0.43,
                    "rank": 1,
                    "rerank_reason": {"token_overlap": 1.0},
                }
            ],
            "metadata": {
                "answer_mode": "grounded_context",
                "rerank": rerank,
                "rerank_top_k": rerank_top_k,
                "limit": limit,
                "score_threshold": score_threshold,
            },
        }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(rag_api_router.router, prefix="/api/v1/rag")
    return TestClient(app)


def test_retrieve_response_uses_strong_contract(monkeypatch):
    monkeypatch.setattr(
        rag_api_router,
        "build_default_retrieval_service",
        lambda: FakeRetrievalService(),
    )

    response = _client().post(
        "/api/v1/rag/retrieve",
        json={"query": "M10球头杆长是多少", "domain": "spec", "limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "spec"
    assert payload["result_count"] == 1
    assert payload["results"][0]["chunk_id"] == "chunk-001"
    assert payload["results"][0]["rerank_reason"] == {"token_overlap": 1.0}
    assert payload["metadata"] == {
        "rerank_enabled": True,
        "rerank_top_k": 3,
        "limit": 3,
        "score_threshold": None,
        "embedding_dimension": 8,
    }


def test_answer_response_exposes_top_level_status_fields(monkeypatch):
    monkeypatch.setattr(
        rag_api_router,
        "build_default_answer_service",
        lambda: FakeAnswerService(),
    )

    response = _client().post(
        "/api/v1/rag/answer",
        json={"query": "M10球头杆长是多少", "domain": "spec", "limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_strategy_mode"] == "single_primary"
    assert payload["answer_safety_blocked"] is False
    assert payload["answer_handoff_required"] is False
    assert payload["answer_boundary_notes"] == []
    assert payload["answer_candidate_modules"] == ["spec"]
    assert payload["sources"][0]["chunk_id"] == "chunk-001"
    assert payload["contexts"][0]["text"].startswith("M10球头")
    assert payload["metadata"]["answer_mode"] == "grounded_context"
    assert isinstance(payload["metadata"]["latency_ms"], int)


def test_answer_refusal_maps_to_handoff_status(monkeypatch):
    monkeypatch.setattr(
        rag_api_router,
        "build_default_answer_service",
        lambda: FakeAnswerService(should_answer=False),
    )

    response = _client().post(
        "/api/v1/rag/answer",
        json={"query": "未知问题", "domain": "spec"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["should_answer"] is False
    assert payload["answer_strategy_mode"] == "handoff_required"
    assert payload["answer_safety_blocked"] is False
    assert payload["answer_handoff_required"] is True
    assert payload["answer_boundary_notes"] == ["知识库召回置信度不足，建议转人工确认。"]
    assert payload["metadata"]["refusal_reason"] == "low_confidence"


def test_request_validation_returns_422_for_invalid_contract_values():
    response = _client().post(
        "/api/v1/rag/retrieve",
        json={"query": "M10", "domain": "bad-domain", "limit": 999},
    )

    assert response.status_code == 422
    locations = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert ("body", "domain") in locations
    assert ("body", "limit") in locations


def test_openapi_schema_exposes_typed_response_models():
    schema = _client().get("/openapi.json").json()
    schemas = schema["components"]["schemas"]

    retrieve = schemas["RagRetrieveResponse"]["properties"]
    assert retrieve["results"]["items"]["$ref"].endswith("/RagChunkResult")
    assert retrieve["metadata"]["$ref"].endswith("/RagRetrieveMetadata")

    answer = schemas["RagAnswerResponse"]["properties"]
    assert answer["sources"]["items"]["$ref"].endswith("/RagSource")
    assert answer["contexts"]["items"]["$ref"].endswith("/RagContext")
    assert answer["metadata"]["$ref"].endswith("/RagAnswerMetadata")
    assert "answer_strategy_mode" in answer
    assert "answer_safety_blocked" in answer
    assert "answer_handoff_required" in answer
    assert "answer_boundary_notes" in answer
    assert "answer_candidate_modules" in answer
