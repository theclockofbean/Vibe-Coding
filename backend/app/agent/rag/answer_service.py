from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.agent.llm.schemas import LLMRequest
from app.agent.rag.retrieval_service import (
    RagRetrievalService,
    build_default_retrieval_service,
)


# =========================
# Config
# =========================
@dataclass
class RagAnswerConfig:
    default_limit: int = 5
    default_rerank: bool = True
    default_rerank_top_k: Optional[int] = 3
    min_confidence: float = 0.2
    max_answer_chars: int = 800
    max_context_chars: int = 1200


# =========================
# DTOs (STRICT CONTRACT)
# =========================
class RagChunkResult(BaseModel):
    chunk_id: str
    document_id: str
    domain: str

    text: str

    source: str | None = None
    source_type: str | None = None

    score: float
    original_score: float | None = None
    rerank_score: float | None = None
    rank: int


class RagAnswerMetadata(BaseModel):
    answer_mode: str
    rerank: bool
    rerank_top_k: int
    limit: int
    score_threshold: float | None = None


# =========================
# Service
# =========================
class RagAnswerService:

    def __init__(
        self,
        *,
        retrieval_service: Optional[RagRetrievalService] = None,
        llm_client: Any = None,
        config: Optional[RagAnswerConfig] = None,
    ) -> None:
        self.retrieval_service = retrieval_service or build_default_retrieval_service()
        self.llm_client = llm_client
        self.config = config or RagAnswerConfig()

    # =========================
    # Public API
    # =========================
    def answer(
        self,
        *,
        query: str,
        domain: Optional[str] = None,
        limit: Optional[int] = None,
        score_threshold: Optional[float] = None,
        rerank: Optional[bool] = None,
        rerank_top_k: Optional[int] = None,
    ) -> Dict[str, Any]:

        normalized_query = self._normalize_query(query)

        effective_limit = limit or self.config.default_limit
        effective_rerank = self.config.default_rerank if rerank is None else rerank
        effective_rerank_top_k = (
            self.config.default_rerank_top_k if rerank_top_k is None else rerank_top_k
        )

        raw_contexts = self.retrieval_service.retrieve(
            query=normalized_query,
            domain=domain,
            limit=effective_limit,
            score_threshold=score_threshold,
            rerank=effective_rerank,
            rerank_top_k=effective_rerank_top_k,
        )

        contexts = [RagChunkResult(**item) for item in raw_contexts]

        confidence = self._calculate_confidence(contexts)

        if not contexts:
            return self._build_refusal_answer(
                query=normalized_query,
                domain=domain,
                confidence=confidence,
                reason="no_context",
            )

        if confidence < self.config.min_confidence:
            return self._build_refusal_answer(
                query=normalized_query,
                domain=domain,
                confidence=confidence,
                reason="low_confidence",
                contexts=contexts,
            )

        answer_text = self._build_llm_answer(
            query=normalized_query,
            contexts=contexts,
        )

        metadata = RagAnswerMetadata(
            answer_mode="grounded_context",
            rerank=effective_rerank,
            rerank_top_k=effective_rerank_top_k,
            limit=effective_limit,
            score_threshold=score_threshold,
        )

        return {
            "query": normalized_query,
            "domain": domain,
            "answer": answer_text,
            "should_answer": True,
            "confidence": confidence,
            "source_count": len(contexts),

            "sources": contexts,
            "contexts": contexts,
            "metadata": metadata,
        }

    # =========================
    # LLM
    # =========================
    def _build_llm_answer(
        self,
        *,
        query: str,
        contexts: List[RagChunkResult],
    ) -> str:

        if not self.llm_client:
            return self._build_grounded_answer(contexts)

        try:
            request = LLMRequest(
                task_type="rag_answer",
                user_text=query,
                request_id="rag",
                context_blocks=[self._build_prompt(query, contexts)],
                retrieved_chunks=[c.model_dump() for c in contexts],
                structured_facts={},
                business_rules=[],
                forbidden_commitments=(),
            )

            response = self.llm_client.generate(request)
            content = self._extract_llm_content(response)

            if not content:
                return self._build_grounded_answer(contexts)

            return str(content)

        except Exception:
            return self._build_grounded_answer(contexts)

    # =========================
    # Prompt
    # =========================
    def _build_prompt(
        self,
        query: str,
        contexts: List[RagChunkResult],
    ) -> str:

        context_text = "\n\n".join(
            [
                f"[{i+1}] {c.text}"
                for i, c in enumerate(contexts[:5])
            ]
        )

        return f"""
你是汽车配件知识助手，只能基于知识库资料回答问题。

【用户问题】
{query}

【知识库资料】
{context_text}

【要求】
1. 只能基于知识库回答
2. 不允许编造信息
3. 如果资料不足，说无法确定
4. 简洁直接回答
"""

    # =========================
    # Fallback answer
    # =========================
    def _build_grounded_answer(self, contexts: List[RagChunkResult]) -> str:
        primary = contexts[0]
        text = primary.text

        if len(text) > self.config.max_answer_chars:
            text = text[: self.config.max_answer_chars] + "..."

        return f"根据知识库资料：{text}"

    # =========================
    # Confidence
    # =========================
    def _calculate_confidence(self, contexts: List[RagChunkResult]) -> float:
        if not contexts:
            return 0.0

        first = contexts[0]
        score = first.rerank_score or first.score

        try:
            return round(float(score), 6)
        except Exception:
            return 0.0

    # =========================
    # Utils
    # =========================
    def _normalize_query(self, query: str) -> str:
        q = str(query or "").replace("\ufeff", "").strip()
        if not q:
            raise ValueError("query must not be empty")
        return q

    def _extract_llm_content(self, response: Any) -> Optional[str]:
        if isinstance(response, dict):
            try:
                return response["choices"][0]["message"]["content"]
            except Exception:
                return None

        try:
            return response.choices[0].message.content
        except Exception:
            return getattr(response, "content", None)


# =========================
# Factory
# =========================
def build_default_answer_service():
    from app.agent.llm.factory import build_llm_client

    return RagAnswerService(
        retrieval_service=build_default_retrieval_service(),
        llm_client=build_llm_client(),
    )
