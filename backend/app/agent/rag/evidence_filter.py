"""RAG evidence filter.

EvidenceFilter validates retrieved chunks before they enter AgentState.

It does not call Qdrant, call an LLM, generate answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.rag.schemas import (
    RetrievalResult,
    RetrievedChunk,
    validate_module,
)


@dataclass(frozen=True)
class EvidenceFilterResult:
    """Filtered evidence result."""

    safe_chunks: list[RetrievedChunk] = field(default_factory=list)
    rejected_chunks: list[RetrievedChunk] = field(default_factory=list)
    source_references: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_retrieval_result(self) -> RetrievalResult:
        """Convert to RetrievalResult."""

        return RetrievalResult(
            chunks=list(self.safe_chunks),
            rejected_chunks=list(self.rejected_chunks),
            warnings=list(self.warnings),
            metadata=dict(self.metadata),
        )

    def to_retrieved_chunk_dicts(self) -> list[dict[str, Any]]:
        """Return safe chunk dicts."""

        return [
            chunk.to_dict()
            for chunk in self.safe_chunks
        ]


@dataclass(frozen=True)
class RAGEvidenceFilter:
    """Deterministic RAG evidence filter."""

    score_threshold: float = 0.2
    strict_module_match: bool = True
    require_verified_for_high_risk: bool = True

    def __post_init__(self) -> None:
        """Validate filter config."""

        if self.score_threshold < 0 or self.score_threshold > 1:
            raise ValueError("score_threshold must be between 0 and 1")

    def filter_chunks(
        self,
        *,
        chunks: list[RetrievedChunk],
        selected_module: str | None,
        commitment_context: bool = False,
        min_score: float | None = None,
    ) -> EvidenceFilterResult:
        """Filter retrieved chunks before AgentState injection."""

        if selected_module is not None:
            validate_module(selected_module)

        score_threshold = self.score_threshold if min_score is None else min_score

        if score_threshold < 0 or score_threshold > 1:
            raise ValueError("min_score must be between 0 and 1")

        safe_chunks: list[RetrievedChunk] = []
        rejected_chunks: list[RetrievedChunk] = []
        warnings: list[str] = []
        risk_reasons: list[str] = []

        for chunk in chunks:
            rejection_reasons = self._get_rejection_reasons(
                chunk=chunk,
                selected_module=selected_module,
                commitment_context=commitment_context,
                score_threshold=score_threshold,
            )

            if rejection_reasons:
                rejected_chunks.append(chunk)
                warnings.extend(
                    f"rag_chunk_rejected:{chunk.chunk_id}:{reason}"
                    for reason in rejection_reasons
                )
                risk_reasons.extend(
                    f"rag_evidence_filter:{chunk.chunk_id}:{reason}"
                    for reason in rejection_reasons
                    if _is_risk_reason(reason)
                )
                continue

            safe_chunks.append(chunk)

        sorted_safe_chunks = sorted(
            safe_chunks,
            key=lambda item: item.score,
            reverse=True,
        )

        source_references = [
            chunk.to_source_reference()
            for chunk in sorted_safe_chunks
        ]

        metadata = {
            "evidence_filter": "RAGEvidenceFilter",
            "score_threshold": score_threshold,
            "strict_module_match": self.strict_module_match,
            "require_verified_for_high_risk": self.require_verified_for_high_risk,
            "commitment_context": commitment_context,
            "selected_module": selected_module,
            "input_count": len(chunks),
            "safe_count": len(sorted_safe_chunks),
            "rejected_count": len(rejected_chunks),
        }

        return EvidenceFilterResult(
            safe_chunks=sorted_safe_chunks,
            rejected_chunks=rejected_chunks,
            source_references=source_references,
            warnings=_deduplicate_text(warnings),
            risk_reasons=_deduplicate_text(risk_reasons),
            metadata=metadata,
        )

    def _get_rejection_reasons(
        self,
        *,
        chunk: RetrievedChunk,
        selected_module: str | None,
        commitment_context: bool,
        score_threshold: float,
    ) -> list[str]:
        """Return rejection reasons for one chunk."""

        reasons: list[str] = []

        if not chunk.is_active:
            reasons.append("inactive")

        if not chunk.allow_answer_reference:
            reasons.append("answer_reference_not_allowed")

        if chunk.score < score_threshold:
            reasons.append("score_below_threshold")

        if (
            self.strict_module_match
            and selected_module is not None
            and chunk.module != "general"
            and chunk.module != selected_module
        ):
            reasons.append("module_mismatch")

        if (
            self.require_verified_for_high_risk
            and chunk.risk_level == "high"
            and not chunk.is_verified
        ):
            reasons.append("high_risk_unverified")

        if commitment_context and not chunk.allow_commitment_reference:
            reasons.append("commitment_reference_not_allowed")

        return reasons


def filter_retrieved_chunk_dicts(
    *,
    chunks: list[dict[str, Any]],
    selected_module: str | None,
    commitment_context: bool = False,
    score_threshold: float = 0.2,
) -> EvidenceFilterResult:
    """Filter chunk dicts by converting them to RetrievedChunk."""

    retrieved_chunks = [
        _retrieved_chunk_from_dict(chunk)
        for chunk in chunks
    ]

    evidence_filter = RAGEvidenceFilter(
        score_threshold=score_threshold,
    )

    return evidence_filter.filter_chunks(
        chunks=retrieved_chunks,
        selected_module=selected_module,
        commitment_context=commitment_context,
    )


def _retrieved_chunk_from_dict(
    value: dict[str, Any],
) -> RetrievedChunk:
    """Build RetrievedChunk from dict."""

    return RetrievedChunk(
        collection=str(value["collection"]),
        chunk_id=str(value["chunk_id"]),
        source_type=str(value["source_type"]),
        source_name=str(value["source_name"]),
        doc_id=str(value["doc_id"]),
        doc_title=str(value["doc_title"]),
        chunk_index=int(value["chunk_index"]),
        module=str(value["module"]),
        content=str(value["content"]),
        score=float(value["score"]),
        summary=_optional_text(value.get("summary")),
        risk_level=str(value.get("risk_level", "low")),
        is_active=_bool_value(value.get("is_active"), default=True),
        is_verified=_bool_value(value.get("is_verified"), default=False),
        allow_answer_reference=_bool_value(
            value.get("allow_answer_reference"),
            default=True,
        ),
        allow_commitment_reference=_bool_value(
            value.get("allow_commitment_reference"),
            default=False,
        ),
        metadata=_optional_dict(value.get("metadata")),
    )


def _optional_text(value: object) -> str | None:
    """Return optional text."""

    if value is None:
        return None

    return str(value)


def _optional_dict(value: object) -> dict[str, Any]:
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


def _is_risk_reason(reason: str) -> bool:
    """Return whether rejection reason should be treated as risk."""

    return reason in {
        "answer_reference_not_allowed",
        "module_mismatch",
        "high_risk_unverified",
        "commitment_reference_not_allowed",
    }


def _deduplicate_text(values: list[str]) -> list[str]:
    """Deduplicate text list while preserving order."""

    result: list[str] = []

    for value in values:
        if value not in result:
            result.append(value)

    return result