"""RAG retriever contracts and local fallback retriever.

Phase 3-E v0.1 provides Retriever protocol, NullRetriever, and a deterministic
PostgreSQL-backed LocalKnowledgeChunkRetriever.

It does not call Qdrant, call an LLM, generate answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.agent.rag.schemas import RetrievalQuery, RetrievedChunk


class Retriever(Protocol):
    """Retriever protocol."""

    def retrieve(
        self,
        *,
        query: str,
        selected_module: str | None,
        matched_sku: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant chunks."""


@dataclass(frozen=True)
class NullRetriever:
    """No-op retriever for safe fallback and contract tests."""

    reason: str = "retrieval_disabled"

    def retrieve(
        self,
        *,
        query: str,
        selected_module: str | None,
        matched_sku: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return no chunks after validating query contract."""

        RetrievalQuery(
            query=query,
            selected_module=selected_module,
            matched_sku=matched_sku,
            top_k=top_k,
        )

        return []


@dataclass(frozen=True)
class LocalKnowledgeChunkRetriever:
    """Deterministic PostgreSQL-backed local retriever.

    This retriever is intended for local development, regression checks, and
    fallback behavior before Qdrant is connected.
    """

    session: Session
    score_threshold: float = 0.01
    max_candidates: int = 50

    def __post_init__(self) -> None:
        """Validate config."""

        if self.score_threshold < 0 or self.score_threshold > 1:
            raise ValueError("score_threshold must be between 0 and 1")

        if self.max_candidates < 1 or self.max_candidates > 200:
            raise ValueError("max_candidates must be between 1 and 200")

    def retrieve(
        self,
        *,
        query: str,
        selected_module: str | None,
        matched_sku: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve chunks from PostgreSQL metadata table."""

        retrieval_query = RetrievalQuery(
            query=query,
            selected_module=selected_module,
            matched_sku=matched_sku,
            top_k=top_k,
        )

        from app.repositories.knowledge_chunk_repository import (
            KnowledgeChunkRepository,
        )

        repository = KnowledgeChunkRepository(self.session)

        candidate_limit = min(
            max(self.max_candidates, top_k),
            200,
        )

        rows = repository.list_for_retrieval(
            selected_module=retrieval_query.selected_module,
            matched_sku=retrieval_query.matched_sku,
            language=retrieval_query.language,
            limit=candidate_limit,
        )

        scored_chunks: list[RetrievedChunk] = []

        for row in rows:
            score = _local_relevance_score(
                row=row,
                retrieval_query=retrieval_query,
            )

            if score < self.score_threshold:
                continue

            scored_chunks.append(
                _row_to_retrieved_chunk(
                    row=row,
                    score=score,
                )
            )

        sorted_chunks = sorted(
            scored_chunks,
            key=lambda item: item.score,
            reverse=True,
        )

        return [
            chunk.to_dict()
            for chunk in sorted_chunks[:top_k]
        ]


def ensure_retrieved_chunk_dicts(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return sanitized chunk dicts."""

    sanitized_chunks: list[dict[str, Any]] = []

    for chunk in chunks:
        sanitized_chunks.append(
            {
                str(key): value
                for key, value in chunk.items()
            }
        )

    return sanitized_chunks


def _row_to_retrieved_chunk(
    *,
    row: Mapping[str, Any],
    score: float,
) -> RetrievedChunk:
    """Convert repository row to RetrievedChunk."""

    return RetrievedChunk(
        collection=str(row["collection_name"]),
        chunk_id=str(row["chunk_id"]),
        source_type=str(row["source_type"]),
        source_name=str(row["source_name"]),
        doc_id=str(row["doc_id"]),
        doc_title=str(row["doc_title"]),
        chunk_index=int(row["chunk_index"]),
        module=str(row["module"]),
        content=str(row["content"]),
        score=score,
        summary=_optional_text(row.get("summary")),
        risk_level=str(row.get("risk_level", "low")),
        is_active=_bool_value(row.get("is_active"), default=True),
        is_verified=_bool_value(row.get("is_verified"), default=False),
        allow_answer_reference=_bool_value(
            row.get("allow_answer_reference"),
            default=True,
        ),
        allow_commitment_reference=_bool_value(
            row.get("allow_commitment_reference"),
            default=False,
        ),
        metadata=_optional_dict(row.get("metadata")),
    )


def _local_relevance_score(
    *,
    row: Mapping[str, Any],
    retrieval_query: RetrievalQuery,
) -> float:
    """Return deterministic local relevance score in [0, 1]."""

    query_text = _normalize_text(retrieval_query.normalized_query)
    candidate_text = _build_candidate_text(row)

    if not query_text or not candidate_text:
        return 0.0

    overlap_score = _character_overlap_score(
        query_text=query_text,
        candidate_text=candidate_text,
    )

    module_bonus = _module_bonus(
        row=row,
        selected_module=retrieval_query.selected_module,
    )

    sku_bonus = _sku_bonus(
        row=row,
        matched_sku=retrieval_query.matched_sku,
    )

    intent_bonus = _intent_scope_bonus(
        row=row,
        query_text=query_text,
    )

    score = (overlap_score * 0.68) + module_bonus + sku_bonus + intent_bonus

    return min(1.0, round(score, 6))


def _build_candidate_text(
    row: Mapping[str, Any],
) -> str:
    """Build searchable candidate text."""

    parts: list[str] = [
        str(row.get("chunk_id") or ""),
        str(row.get("source_name") or ""),
        str(row.get("doc_id") or ""),
        str(row.get("doc_title") or ""),
        str(row.get("module") or ""),
        str(row.get("content") or ""),
        str(row.get("summary") or ""),
    ]

    sku_scope = _as_str_list(row.get("sku_scope"))
    intent_scope = _as_str_list(row.get("intent_scope"))

    parts.extend(sku_scope)
    parts.extend(intent_scope)

    return _normalize_text(" ".join(parts))


def _character_overlap_score(
    *,
    query_text: str,
    candidate_text: str,
) -> float:
    """Return character-overlap relevance score."""

    query_chars = {
        char
        for char in query_text
        if _is_relevant_char(char)
    }

    if not query_chars:
        return 0.0

    candidate_chars = {
        char
        for char in candidate_text
        if _is_relevant_char(char)
    }

    if not candidate_chars:
        return 0.0

    overlap = query_chars.intersection(candidate_chars)

    return len(overlap) / len(query_chars)


def _module_bonus(
    *,
    row: Mapping[str, Any],
    selected_module: str | None,
) -> float:
    """Return module relevance bonus."""

    if selected_module is None:
        return 0.0

    module = str(row.get("module") or "")

    if module == selected_module:
        return 0.18

    if module == "general":
        return 0.06

    return 0.0


def _sku_bonus(
    *,
    row: Mapping[str, Any],
    matched_sku: str | None,
) -> float:
    """Return SKU relevance bonus."""

    if matched_sku is None:
        return 0.0

    sku_scope = _as_str_list(row.get("sku_scope"))

    if matched_sku in sku_scope:
        return 0.14

    if not sku_scope:
        return 0.03

    return 0.0


def _intent_scope_bonus(
    *,
    row: Mapping[str, Any],
    query_text: str,
) -> float:
    """Return intent-scope relevance bonus."""

    intent_scope = _as_str_list(row.get("intent_scope"))

    if not intent_scope:
        return 0.0

    normalized_intents = [
        _normalize_text(item)
        for item in intent_scope
    ]

    for intent in normalized_intents:
        if intent and intent in query_text:
            return 0.08

    intent_chars = set("".join(normalized_intents))
    query_chars = set(query_text)

    if intent_chars and intent_chars.intersection(query_chars):
        return 0.04

    return 0.0


def _normalize_text(
    value: str,
) -> str:
    """Normalize text for deterministic local matching."""

    return re.sub(r"\s+", "", value.strip().lower())


def _is_relevant_char(
    value: str,
) -> bool:
    """Return whether char should participate in local scoring."""

    return value.isalnum() or "\u4e00" <= value <= "\u9fff"


def _as_str_list(
    value: object,
) -> list[str]:
    """Normalize unknown value to list[str]."""

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
    ]


def _optional_text(
    value: object,
) -> str | None:
    """Return optional text."""

    if value is None:
        return None

    return str(value)


def _optional_dict(
    value: object,
) -> dict[str, Any]:
    """Return optional dict."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _bool_value(
    value: object,
    *,
    default: bool,
) -> bool:
    """Return bool from unknown value."""

    if isinstance(value, bool):
        return value

    return default