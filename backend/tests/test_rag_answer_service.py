from __future__ import annotations

import pytest

from app.agent.rag.answer_service import RagAnswerConfig, RagAnswerService


class FakeRetrievalService:
    def __init__(self, results):
        self.results = results
        self.calls = []

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
        self.calls.append(
            {
                "query": query,
                "domain": domain,
                "limit": limit,
                "score_threshold": score_threshold,
                "rerank": rerank,
                "rerank_top_k": rerank_top_k,
            }
        )
        return self.results


def test_answer_builds_grounded_response_with_sources():
    fake_retrieval = FakeRetrievalService(
        [
            {
                "text": "M10球头，杆长60mm，适合规格查询。",
                "chunk_id": "chunk-001",
                "document_id": "doc-001",
                "domain": "spec",
                "source": "manual-test.md",
                "source_type": "doc",
                "score": 0.36,
                "original_score": 0.36,
                "rerank_score": 0.43,
                "rank": 1,
                "rerank_reason": {"token_overlap": 1.0},
            }
        ]
    )

    service = RagAnswerService(
        retrieval_service=fake_retrieval,
        config=RagAnswerConfig(min_confidence=0.2),
    )

    result = service.answer(query=" M10球头杆长是多少 ", domain="spec", limit=3)

    assert result["query"] == "M10球头杆长是多少"
    assert result["domain"] == "spec"
    assert result["should_answer"] is True
    assert result["confidence"] == 0.43
    assert result["source_count"] == 1
    assert result["answer"].startswith("根据知识库资料：")
    assert "M10球头" in result["answer"]
    assert result["sources"][0]["chunk_id"] == "chunk-001"
    assert result["contexts"][0]["rerank_reason"] == {"token_overlap": 1.0}
    assert result["metadata"]["answer_mode"] == "grounded_context"


def test_answer_refuses_when_no_context():
    fake_retrieval = FakeRetrievalService([])
    service = RagAnswerService(retrieval_service=fake_retrieval)

    result = service.answer(query="知识库没有的问题", domain="spec")

    assert result["should_answer"] is False
    assert result["confidence"] == 0.0
    assert result["source_count"] == 0
    assert result["sources"] == []
    assert result["contexts"] == []
    assert result["metadata"]["answer_mode"] == "refusal"
    assert result["metadata"]["refusal_reason"] == "no_context"


def test_answer_refuses_when_confidence_is_low():
    fake_retrieval = FakeRetrievalService(
        [
            {
                "text": "弱相关内容",
                "chunk_id": "chunk-low",
                "document_id": "doc-low",
                "domain": "spec",
                "source": "weak.md",
                "source_type": "doc",
                "score": 0.05,
                "rerank_score": 0.08,
            }
        ]
    )

    service = RagAnswerService(
        retrieval_service=fake_retrieval,
        config=RagAnswerConfig(min_confidence=0.2),
    )

    result = service.answer(query="M10球头杆长是多少", domain="spec")

    assert result["should_answer"] is False
    assert result["confidence"] == 0.08
    assert result["source_count"] == 1
    assert result["metadata"]["answer_mode"] == "refusal"
    assert result["metadata"]["refusal_reason"] == "low_confidence"


def test_answer_rejects_empty_query():
    service = RagAnswerService(retrieval_service=FakeRetrievalService([]))

    with pytest.raises(ValueError, match="query must not be empty"):
        service.answer(query="   ", domain="spec")


def test_answer_passes_retrieval_parameters():
    fake_retrieval = FakeRetrievalService([])
    service = RagAnswerService(retrieval_service=fake_retrieval)

    service.answer(
        query="M10球头杆长是多少",
        domain="spec",
        limit=7,
        score_threshold=0.3,
        rerank=False,
        rerank_top_k=2,
    )

    assert fake_retrieval.calls == [
        {
            "query": "M10球头杆长是多少",
            "domain": "spec",
            "limit": 7,
            "score_threshold": 0.3,
            "rerank": False,
            "rerank_top_k": 2,
        }
    ]
