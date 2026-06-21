from __future__ import annotations

import time
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.rag.answer_service import build_default_answer_service
from app.agent.rag.retrieval_service import build_default_retrieval_service


router = APIRouter(
    tags=["rag"],
)


class RagDomain(str, Enum):
    spec = "spec"
    price = "price"
    logistics = "logistics"
    quality = "quality"
    general = "general"


class AnswerStrategyMode(str, Enum):
    single_primary = "single_primary"
    primary_with_boundary_note = "primary_with_boundary_note"
    split_required = "split_required"
    safety_blocked = "safety_blocked"
    handoff_required = "handoff_required"


class RagRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="User query text.")
    domain: RagDomain | None = Field(default=None, description="Optional knowledge domain.")
    limit: int = Field(default=5, ge=1, le=20, description="Top-K retrieval limit.")
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional vector score threshold.",
    )
    rerank: bool = Field(default=True, description="Whether to apply reranker.")
    rerank_top_k: int | None = Field(
        default=3,
        ge=1,
        le=20,
        description="Keep top K after reranking.",
    )


class RagAnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="User query text.")
    domain: RagDomain | None = Field(default=None, description="Optional knowledge domain.")
    limit: int = Field(default=5, ge=1, le=20, description="Top-K retrieval limit.")
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional vector score threshold.",
    )
    rerank: bool = Field(default=True, description="Whether to apply reranker.")
    rerank_top_k: int | None = Field(
        default=3,
        ge=1,
        le=20,
        description="Keep top K after reranking.",
    )


class RagChunkResult(BaseModel):
    chunk_id: str = ""
    document_id: str = ""
    domain: RagDomain | str = ""
    text: str = ""
    source: str = ""
    source_type: str = ""
    score: float = 0.0
    original_score: float | None = None
    rerank_score: float | None = None
    rank: int = 0
    rerank_reason: dict[str, Any] | None = None


class RagRetrieveMetadata(BaseModel):
    rerank_enabled: bool
    rerank_top_k: int | None
    limit: int
    score_threshold: float | None = None
    embedding_dimension: int


class RagRetrieveResponse(BaseModel):
    query: str
    domain: RagDomain | None
    result_count: int
    results: list[RagChunkResult]
    metadata: RagRetrieveMetadata


class RagSource(BaseModel):
    index: int = 0
    chunk_id: str = ""
    document_id: str = ""
    domain: RagDomain | str = ""
    source: str = ""
    source_type: str = ""
    score: float = 0.0
    original_score: float | None = None
    rerank_score: float | None = None
    rank: int = 0


class RagContext(RagSource):
    text: str = ""
    rerank_reason: dict[str, Any] | None = None


class RagAnswerMetadata(BaseModel):
    answer_mode: str
    rerank: bool
    rerank_top_k: int | None
    limit: int
    score_threshold: float | None = None
    latency_ms: int
    refusal_reason: str | None = None


class RagAnswerResponse(BaseModel):
    query: str
    domain: RagDomain | None
    answer: str
    should_answer: bool
    confidence: float
    source_count: int
    sources: list[RagSource]
    contexts: list[RagContext]
    metadata: RagAnswerMetadata
    answer_strategy_mode: AnswerStrategyMode
    answer_safety_blocked: bool
    answer_handoff_required: bool
    answer_boundary_notes: list[str] = Field(default_factory=list)
    answer_candidate_modules: list[RagDomain] = Field(default_factory=list)


@router.post(
    "/retrieve",
    response_model=RagRetrieveResponse,
)
def retrieve_rag_contexts(request: RagRetrieveRequest) -> RagRetrieveResponse:
    """
    Retrieve RAG contexts.

    Contract:
    - Does not generate answer.
    - Does not call LLM.
    - Only returns retrieval/rerank results for debugging and frontend inspection.
    """

    try:
        service = build_default_retrieval_service()

        results = service.retrieve(
            query=request.query,
            domain=request.domain.value if request.domain else None,
            limit=request.limit,
            score_threshold=request.score_threshold,
            rerank=request.rerank,
            rerank_top_k=request.rerank_top_k,
        )

        return RagRetrieveResponse(
            query=request.query,
            domain=request.domain,
            result_count=len(results),
            results=[RagChunkResult(**item) for item in results],
            metadata=RagRetrieveMetadata(
                rerank_enabled=request.rerank,
                rerank_top_k=request.rerank_top_k,
                limit=request.limit,
                score_threshold=request.score_threshold,
                embedding_dimension=_get_embedding_dimension(service),
            ),
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG retrieval failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post(
    "/answer",
    response_model=RagAnswerResponse,
)
def answer_with_rag(request: RagAnswerRequest) -> RagAnswerResponse:
    """
    Generate grounded RAG answer.

    Contract:
    - Uses RagAnswerService.
    - Keeps sources and contexts.
    - Does not modify Workflow state.
    - Current answer mode is grounded_context until LLM grounded generation is added.
    """

    try:
        started_at = time.perf_counter()
        service = build_default_answer_service()

        result = service.answer(
            query=request.query,
            domain=request.domain.value if request.domain else None,
            limit=request.limit,
            score_threshold=request.score_threshold,
            rerank=request.rerank,
            rerank_top_k=request.rerank_top_k,
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        metadata = _build_answer_metadata(result, request, latency_ms)
        strategy_mode = _resolve_answer_strategy_mode(result)

        return RagAnswerResponse(
            query=str(result.get("query") or request.query),
            domain=result.get("domain"),
            answer=str(result.get("answer") or ""),
            should_answer=bool(result.get("should_answer")),
            confidence=float(result.get("confidence") or 0.0),
            source_count=int(result.get("source_count") or 0),
            sources=[
                RagSource(**_model_to_dict(item))
                for item in _list_result_items(result.get("sources"))
            ],
            contexts=[
                RagContext(**_model_to_dict(item))
                for item in _list_result_items(result.get("contexts"))
            ],
            metadata=metadata,
            answer_strategy_mode=strategy_mode,
            answer_safety_blocked=False,
            answer_handoff_required=strategy_mode == AnswerStrategyMode.handoff_required,
            answer_boundary_notes=_resolve_answer_boundary_notes(result),
            answer_candidate_modules=_resolve_answer_candidate_modules(result),
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG answer failed: {type(exc).__name__}: {exc}",
        ) from exc


def _model_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, BaseModel):
        return item.model_dump()

    if isinstance(item, dict):
        return item

    return {}


def _list_result_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    return []


def _get_embedding_dimension(service: Any) -> int:
    embedding_service = getattr(service, "embedding_service", None)
    vector_size = getattr(embedding_service, "vector_size", None)

    if isinstance(vector_size, int) and vector_size > 0:
        return vector_size

    client = getattr(embedding_service, "client", None)
    client_dimension = getattr(client, "dimension", None)

    if isinstance(client_dimension, int) and client_dimension > 0:
        return client_dimension

    return 0


def _build_answer_metadata(
    result: dict[str, Any],
    request: RagAnswerRequest,
    latency_ms: int,
) -> RagAnswerMetadata:
    raw_metadata = result.get("metadata")
    metadata = _model_to_dict(raw_metadata)

    return RagAnswerMetadata(
        answer_mode=str(metadata.get("answer_mode") or "unknown"),
        rerank=bool(metadata.get("rerank", request.rerank)),
        rerank_top_k=metadata.get("rerank_top_k", request.rerank_top_k),
        limit=int(metadata.get("limit") or request.limit),
        score_threshold=metadata.get("score_threshold", request.score_threshold),
        latency_ms=latency_ms,
        refusal_reason=metadata.get("refusal_reason"),
    )


def _resolve_answer_strategy_mode(result: dict[str, Any]) -> AnswerStrategyMode:
    if bool(result.get("should_answer")):
        return AnswerStrategyMode.single_primary

    return AnswerStrategyMode.handoff_required


def _resolve_answer_boundary_notes(result: dict[str, Any]) -> list[str]:
    if bool(result.get("should_answer")):
        return []

    metadata = _model_to_dict(result.get("metadata"))
    refusal_reason = metadata.get("refusal_reason")

    if refusal_reason == "no_context":
        return ["知识库未检索到可靠依据，建议转人工确认。"]

    if refusal_reason == "low_confidence":
        return ["知识库召回置信度不足，建议转人工确认。"]

    return ["当前问题无法由通用 RAG 链路可靠回答，建议转人工确认。"]


def _resolve_answer_candidate_modules(result: dict[str, Any]) -> list[RagDomain]:
    try:
        return [RagDomain(result["domain"])]
    except Exception:
        return []
