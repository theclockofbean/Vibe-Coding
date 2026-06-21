from __future__ import annotations

from app.agent.routing.rag_workflow_adapter import (
    RagWorkflowAdapter,
    build_default_rag_workflow_adapter,
)


def test_adapter_builds_agent_state_patch_for_grounded_answer():
    adapter = build_default_rag_workflow_adapter()

    rag_result = {
        "query": "SKU006螺纹规格和杆长是多少",
        "domain": "spec",
        "answer": "SKU006钛合金磨砂球头，螺纹规格M10×1.5，杆长42mm。",
        "should_answer": True,
        "confidence": 0.76,
        "sources": [
            {
                "index": 1,
                "chunk_id": "chunk-001",
                "document_id": "doc-001",
                "domain": "spec",
                "source": "spec_questions.xlsx",
                "source_type": "qa",
                "score": 0.76,
                "rerank_score": 0.8,
                "rank": 1,
            }
        ],
        "contexts": [
            {
                "index": 1,
                "text": "QA编号：SPEC0002...",
                "chunk_id": "chunk-001",
                "document_id": "doc-001",
                "domain": "spec",
                "source": "spec_questions.xlsx",
                "source_type": "qa",
                "score": 0.76,
                "rerank_score": 0.8,
                "rank": 1,
                "metadata": {
                    "row": {
                        "handoff_required": False,
                        "risk_flags": "",
                    }
                },
            }
        ],
        "metadata": {
            "answer_mode": "grounded_context",
        },
    }

    patch = adapter.adapt_answer_to_state_patch(
        rag_result=rag_result,
        current_state={
            "metadata": {
                "existing": "ok",
            }
        },
    )

    assert patch["selected_module"] == "spec"
    assert patch["answer_text"] == rag_result["answer"]
    assert patch["handoff_required"] is False
    assert patch["human_handoff"] is False
    assert patch["warnings"] == []
    assert patch["risk_reasons"] == []
    assert len(patch["retrieved_chunks"]) == 1
    assert len(patch["source_references"]) == 1
    assert patch["retrieved_chunks"][0]["chunk_id"] == "chunk-001"
    assert patch["source_references"][0]["source_id"] == "chunk-001"
    assert patch["metadata"]["existing"] == "ok"
    assert patch["metadata"]["rag_workflow_adapter_used"] is True
    assert patch["metadata"]["rag_answer_mode"] == "grounded_context"
    assert patch["metadata"]["rag_selected_module"] == "spec"
    assert patch["metadata"]["rag_confidence"] == 0.76


def test_adapter_marks_handoff_for_refusal_result():
    adapter = build_default_rag_workflow_adapter()

    rag_result = {
        "query": "未知问题",
        "domain": "spec",
        "answer": "暂时没有找到可靠依据",
        "should_answer": False,
        "confidence": 0.1,
        "sources": [],
        "contexts": [],
        "metadata": {
            "answer_mode": "refusal",
            "refusal_reason": "low_confidence",
        },
    }

    patch = adapter.adapt_answer_to_state_patch(
        rag_result=rag_result,
        current_state={},
    )

    assert patch["selected_module"] == "spec"
    assert patch["handoff_required"] is True
    assert patch["human_handoff"] is True
    assert "rag_answer_not_allowed" in patch["warnings"]
    assert "rag_low_confidence" in patch["warnings"]
    assert "rag_refusal_reason:low_confidence" in patch["warnings"]
    assert patch["metadata"]["rag_handoff_required"] is True


def test_adapter_marks_handoff_for_context_risk_flags():
    adapter = build_default_rag_workflow_adapter()

    rag_result = {
        "query": "能不能保证适配高尔夫",
        "domain": "spec",
        "answer": "车型适配需要人工核验。",
        "should_answer": True,
        "confidence": 0.82,
        "sources": [],
        "contexts": [
            {
                "domain": "spec",
                "text": "车型适配需要核验",
                "metadata": {
                    "row": {
                        "handoff_required": True,
                        "risk_flags": "vehicle_fitment_unverified",
                    }
                },
            }
        ],
        "metadata": {
            "answer_mode": "grounded_context",
        },
    }

    patch = adapter.adapt_answer_to_state_patch(
        rag_result=rag_result,
        current_state={},
    )

    assert patch["selected_module"] == "spec"
    assert patch["handoff_required"] is True
    assert patch["human_handoff"] is True
    assert "vehicle_fitment_unverified" in patch["risk_reasons"]
    assert "rag_context_handoff_required" in patch["risk_reasons"]


def test_adapter_falls_back_to_current_state_module():
    adapter = RagWorkflowAdapter()

    rag_result = {
        "query": "测试问题",
        "answer": "测试回答",
        "should_answer": True,
        "confidence": 0.9,
        "sources": [],
        "contexts": [],
        "metadata": {},
    }

    patch = adapter.adapt_answer_to_state_patch(
        rag_result=rag_result,
        current_state={
            "selected_module": "quality",
        },
    )

    assert patch["selected_module"] == "quality"


def test_adapter_returns_none_module_when_no_valid_module():
    adapter = RagWorkflowAdapter()

    rag_result = {
        "query": "测试问题",
        "domain": "unknown",
        "answer": "测试回答",
        "should_answer": True,
        "confidence": 0.9,
        "sources": [],
        "contexts": [],
        "metadata": {},
    }

    patch = adapter.adapt_answer_to_state_patch(
        rag_result=rag_result,
        current_state={},
    )

    assert patch["selected_module"] is None


def test_apply_rag_answer_to_workflow_state_merges_patch_with_fake_service(monkeypatch):
    from app.agent.routing import rag_workflow_adapter

    class FakeAnswerService:
        def answer(
            self,
            *,
            query,
            domain=None,
            limit=3,
            score_threshold=None,
            rerank=True,
            rerank_top_k=3,
        ):
            return {
                "query": query,
                "domain": domain,
                "answer": "SKU006钛合金磨砂球头，螺纹规格M10×1.5，杆长42mm。",
                "should_answer": True,
                "confidence": 0.88,
                "source_count": 1,
                "sources": [
                    {
                        "index": 1,
                        "chunk_id": "chunk-001",
                        "document_id": "doc-001",
                        "domain": domain,
                        "source": "spec_questions.xlsx",
                        "source_type": "qa",
                        "score": 0.88,
                    }
                ],
                "contexts": [
                    {
                        "index": 1,
                        "text": "SKU006钛合金磨砂球头，螺纹规格M10×1.5，杆长42mm。",
                        "chunk_id": "chunk-001",
                        "document_id": "doc-001",
                        "domain": domain,
                        "source": "spec_questions.xlsx",
                        "source_type": "qa",
                        "score": 0.88,
                    }
                ],
                "metadata": {
                    "answer_mode": "grounded_context",
                },
            }

    monkeypatch.setattr(
        rag_workflow_adapter,
        "build_default_answer_service",
        lambda: FakeAnswerService(),
        raising=False,
    )

    state = {
        "user_text": "SKU006螺纹规格和杆长是多少",
        "selected_module": "spec",
        "metadata": {
            "existing": "ok",
        },
        "warnings": [],
        "risk_reasons": [],
        "retrieved_chunks": [],
        "source_references": [],
        "handoff_required": False,
        "human_handoff": False,
    }

    adapter = build_default_rag_workflow_adapter()
    adapter.answer_service = FakeAnswerService()

    result = rag_workflow_adapter.apply_rag_answer_to_workflow_state(
        state=state,
        limit=3,
        rerank=True,
        rerank_top_k=2,
        adapter=adapter,
    )

    assert result["selected_module"] == "spec"
    assert result["answer_text"].startswith("SKU006钛合金")
    assert result["handoff_required"] is False
    assert result["human_handoff"] is False
    assert len(result["retrieved_chunks"]) == 1
    assert len(result["source_references"]) == 1
    assert result["metadata"]["existing"] == "ok"
    assert result["metadata"]["rag_workflow_integration_used"] is True
    assert result["metadata"]["rag_workflow_integration_error"] is None
    assert result["metadata"]["rag_workflow_query"] == "SKU006螺纹规格和杆长是多少"
    assert result["metadata"]["rag_workflow_domain"] == "spec"


def test_apply_rag_answer_to_workflow_state_handles_empty_query():
    from app.agent.routing.rag_workflow_adapter import apply_rag_answer_to_workflow_state

    result = apply_rag_answer_to_workflow_state(
        state={
            "selected_module": "spec",
            "metadata": {},
        }
    )

    assert result["handoff_required"] is True
    assert result["human_handoff"] is True
    assert "rag_workflow_empty_query" in result["warnings"]
    assert result["metadata"]["rag_workflow_integration_used"] is False
    assert result["metadata"]["rag_workflow_integration_error"] == "empty_query"
