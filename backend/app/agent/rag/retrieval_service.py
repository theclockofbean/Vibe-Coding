from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.agent.rag.chunk_vector_store import ChunkVectorStore, build_default_chunk_vector_store
from app.agent.rag.embedding_service import EmbeddingService, build_default_embedding_service
from app.agent.rag.calibrated_reranker import CalibratedReranker

@dataclass
class RetrievalConfig:
    default_limit: int = 5
    default_rerank: bool = True
    default_rerank_top_k: Optional[int] = None


class RagRetrievalService:
    """
    RAG 检索服务。

    职责：
    1. 将 query 转为 embedding vector
    2. 从 Qdrant 检索候选 chunk
    3. 可选执行 rule-based rerank
    4. 返回标准化检索结果

    设计边界：
    - 不负责生成答案
    - 不负责 Prompt 拼接
    - 不直接绑定 FastAPI / Workflow
    - 作为后续 RAG Answer Service 和 Workflow 的基础服务
    """

    def __init__(
        self,
        *,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[ChunkVectorStore] = None,
        reranker: Optional[CalibratedReranker] = None,
        config: Optional[RetrievalConfig] = None,
    ) -> None:
        self.embedding_service = embedding_service or build_default_embedding_service()
        self.vector_store = vector_store or build_default_chunk_vector_store()
        self.reranker = reranker or CalibratedReranker()
        self.config = config or RetrievalConfig()

    def retrieve(
        self,
        *,
        query: str,
        domain: Optional[str] = None,
        limit: Optional[int] = None,
        score_threshold: Optional[float] = None,
        rerank: Optional[bool] = None,
        rerank_top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        normalized_query = self._normalize_query(query)
        effective_limit = self._normalize_limit(limit)
        effective_rerank = self.config.default_rerank if rerank is None else rerank
        effective_rerank_top_k = (
            self.config.default_rerank_top_k
            if rerank_top_k is None
            else self._normalize_top_k(rerank_top_k)
        )

        query_vector = self.embedding_service.embed_text(normalized_query)

        results = self.vector_store.search_as_dicts(
            query_vector=query_vector,
            domain=domain,
            limit=effective_limit,
            score_threshold=score_threshold,
        )

        reranked = results

        if effective_rerank:
            reranked = self.reranker.rerank(
                query=normalized_query,
                items=results,
                domain=domain,
                top_k=effective_rerank_top_k,
            ) or results

        results = self._normalize_rerank_output(reranked)

        return results

    def retrieve_one(
        self,
        *,
        query: str,
        domain: Optional[str] = None,
        score_threshold: Optional[float] = None,
        rerank: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        results = self.retrieve(
            query=query,
            domain=domain,
            limit=1,
            score_threshold=score_threshold,
            rerank=rerank,
            rerank_top_k=1,
        )
        if not results:
            return None
        return results[0]

    def _normalize_query(self, query: str) -> str:
        normalized = str(query or "").replace("\ufeff", "").strip()
        if not normalized:
            raise ValueError("query must not be empty")
        return normalized

    def _normalize_limit(self, limit: Optional[int]) -> int:
        effective_limit = self.config.default_limit if limit is None else int(limit)
        if effective_limit <= 0:
            raise ValueError("limit must be greater than 0")
        return effective_limit

    def _normalize_top_k(self, top_k: int) -> int:
        effective_top_k = int(top_k)
        if effective_top_k <= 0:
            raise ValueError("rerank_top_k must be greater than 0")
        return effective_top_k

    def _normalize_rerank_output(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []

        for i, r in enumerate(results):
            normalized.append({
                **r,

                # 统一字段（前端依赖）
                "original_score": r.get("score"),
                "rerank_score": r.get("calibrated_score"),

                # 排序信息
                "rank": i + 1,

                # 可解释性层（后面 P0-3 会扩展）
                "rerank_reason": {
                    "calibrated": True,
                    "domain": r.get("domain"),
                    "vector_score": r.get("score", 0.0),
                }
            })

        return normalized


def build_default_retrieval_service() -> RagRetrievalService:
    return RagRetrievalService()
