# ruff: noqa: E402,I001
"""Check RAG evidence filter.

This script verifies deterministic filtering of retrieved chunks before
AgentState injection.

It does not call Qdrant, call an LLM, generate answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import (
    RAGEvidenceFilter,
    RetrievedChunk,
    filter_retrieved_chunk_dicts,
)


FORBIDDEN_COMMITMENT_FRAGMENTS: Final[tuple[str, ...]] = (
    "保证最低价",
    "最低价给你",
    "一定包邮",
    "保证到货",
    "今天一定发",
    "保证不坏",
    "保证不生锈",
    "保证不掉漆",
    "保证耐用",
    "能用几年",
    "一年质保",
    "终身质保",
    "七天无理由",
    "一定能退",
    "一定能换",
    "一定赔",
    "一定补发",
    "质量很好",
    "放心用",
    "完全没问题",
)


def build_chunk(
    *,
    chunk_id: str,
    module: str,
    score: float,
    content: str,
    risk_level: str = "low",
    is_active: bool = True,
    is_verified: bool = True,
    allow_answer_reference: bool = True,
    allow_commitment_reference: bool = False,
) -> RetrievedChunk:
    """Build test RetrievedChunk."""

    return RetrievedChunk(
        collection="kb_chunks_v1",
        chunk_id=chunk_id,
        source_type="manual_doc",
        source_name="evidence_filter_check",
        doc_id="evidence_filter_doc",
        doc_title="Evidence Filter Check",
        chunk_index=0,
        module=module,
        content=content,
        score=score,
        risk_level=risk_level,
        is_active=is_active,
        is_verified=is_verified,
        allow_answer_reference=allow_answer_reference,
        allow_commitment_reference=allow_commitment_reference,
    )


def check_safe_filtering() -> bool:
    """Check safe chunks pass filtering."""

    print("=" * 80)
    print("checking safe filtering")

    evidence_filter = RAGEvidenceFilter(score_threshold=0.2)

    chunks = [
        build_chunk(
            chunk_id="safe_quality_001",
            module="quality",
            score=0.86,
            content="阳极氧化是一类常见表面处理说明，不能替代质量承诺。",
            risk_level="medium",
            is_verified=True,
        ),
        build_chunk(
            chunk_id="safe_general_001",
            module="general",
            score=0.72,
            content="RAG 只作为补充说明来源，不作为业务承诺来源。",
            risk_level="low",
            is_verified=False,
        ),
    ]

    result = evidence_filter.filter_chunks(
        chunks=chunks,
        selected_module="quality",
    )

    pprint(result)

    checks = [
        len(result.safe_chunks) == 2,
        len(result.rejected_chunks) == 0,
        len(result.source_references) == 2,
        result.safe_chunks[0].chunk_id == "safe_quality_001",
        result.source_references[0]["source_type"] == "rag_chunk",
        result.metadata["safe_count"] == 2,
        result.metadata["rejected_count"] == 0,
        result.warnings == [],
        result.risk_reasons == [],
    ]

    return all(checks)


def check_rejection_rules() -> bool:
    """Check unsafe chunks are rejected."""

    print("=" * 80)
    print("checking rejection rules")

    evidence_filter = RAGEvidenceFilter(score_threshold=0.2)

    chunks = [
        build_chunk(
            chunk_id="reject_inactive",
            module="quality",
            score=0.9,
            content="inactive chunk",
            is_active=False,
        ),
        build_chunk(
            chunk_id="reject_no_answer_reference",
            module="quality",
            score=0.9,
            content="not allowed for answer reference",
            allow_answer_reference=False,
        ),
        build_chunk(
            chunk_id="reject_low_score",
            module="quality",
            score=0.1,
            content="low score chunk",
        ),
        build_chunk(
            chunk_id="reject_module_mismatch",
            module="price",
            score=0.9,
            content="price chunk should not enter quality retrieval",
        ),
        build_chunk(
            chunk_id="reject_high_risk_unverified",
            module="quality",
            score=0.9,
            content="high risk unverified chunk",
            risk_level="high",
            is_verified=False,
        ),
    ]

    result = evidence_filter.filter_chunks(
        chunks=chunks,
        selected_module="quality",
    )

    pprint(result)

    warnings_text = "\n".join(result.warnings)
    risk_text = "\n".join(result.risk_reasons)

    checks = [
        len(result.safe_chunks) == 0,
        len(result.rejected_chunks) == 5,
        result.metadata["input_count"] == 5,
        result.metadata["safe_count"] == 0,
        result.metadata["rejected_count"] == 5,
        "inactive" in warnings_text,
        "answer_reference_not_allowed" in warnings_text,
        "score_below_threshold" in warnings_text,
        "module_mismatch" in warnings_text,
        "high_risk_unverified" in warnings_text,
        "answer_reference_not_allowed" in risk_text,
        "module_mismatch" in risk_text,
        "high_risk_unverified" in risk_text,
    ]

    return all(checks)


def check_commitment_context_filtering() -> bool:
    """Check commitment-context filtering."""

    print("=" * 80)
    print("checking commitment context filtering")

    evidence_filter = RAGEvidenceFilter(score_threshold=0.2)

    chunks = [
        build_chunk(
            chunk_id="commitment_not_allowed",
            module="general",
            score=0.9,
            content="该 chunk 可说明边界，但不能作为承诺依据。",
            is_verified=True,
            allow_commitment_reference=False,
        ),
        build_chunk(
            chunk_id="commitment_allowed_verified",
            module="general",
            score=0.8,
            content="该 chunk 已验证，但仍只在明确授权场景下作为承诺依据。",
            is_verified=True,
            allow_commitment_reference=True,
        ),
    ]

    result = evidence_filter.filter_chunks(
        chunks=chunks,
        selected_module="quality",
        commitment_context=True,
    )

    pprint(result)

    checks = [
        len(result.safe_chunks) == 1,
        result.safe_chunks[0].chunk_id == "commitment_allowed_verified",
        len(result.rejected_chunks) == 1,
        result.rejected_chunks[0].chunk_id == "commitment_not_allowed",
        any(
            "commitment_reference_not_allowed" in reason
            for reason in result.risk_reasons
        ),
    ]

    return all(checks)


def check_chunk_dict_filtering() -> bool:
    """Check dict input helper."""

    print("=" * 80)
    print("checking chunk dict filtering")

    chunks = [
        build_chunk(
            chunk_id="dict_safe_quality",
            module="quality",
            score=0.77,
            content="dict safe chunk",
        ).to_dict(),
        build_chunk(
            chunk_id="dict_rejected_low_score",
            module="quality",
            score=0.01,
            content="dict rejected low score",
        ).to_dict(),
    ]

    result = filter_retrieved_chunk_dicts(
        chunks=chunks,
        selected_module="quality",
        score_threshold=0.2,
    )

    pprint(result)

    checks = [
        len(result.safe_chunks) == 1,
        result.safe_chunks[0].chunk_id == "dict_safe_quality",
        len(result.rejected_chunks) == 1,
        result.rejected_chunks[0].chunk_id == "dict_rejected_low_score",
    ]

    return all(checks)


def check_empty_input() -> bool:
    """Check empty input behavior."""

    print("=" * 80)
    print("checking empty input")

    evidence_filter = RAGEvidenceFilter(score_threshold=0.2)

    result = evidence_filter.filter_chunks(
        chunks=[],
        selected_module="quality",
    )

    pprint(result)

    checks = [
        result.safe_chunks == [],
        result.rejected_chunks == [],
        result.source_references == [],
        result.warnings == [],
        result.risk_reasons == [],
        result.metadata["input_count"] == 0,
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check filter-generated text has no forbidden commitment fragments."""

    print("=" * 80)
    print("checking no forbidden commitment fragments")

    evidence_filter = RAGEvidenceFilter(score_threshold=0.2)

    result = evidence_filter.filter_chunks(
        chunks=[
            build_chunk(
                chunk_id="boundary_chunk",
                module="general",
                score=0.9,
                content="RAG 只作为说明来源，不作为业务承诺来源。",
            )
        ],
        selected_module="quality",
    )

    serialized = str(result)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def main() -> int:
    """Run RAG evidence filter checks."""

    results = [
        check_safe_filtering(),
        check_rejection_rules(),
        check_commitment_context_filtering(),
        check_chunk_dict_filtering(),
        check_empty_input(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("rag evidence filter check failed")
        return 1

    print("rag evidence filter check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())