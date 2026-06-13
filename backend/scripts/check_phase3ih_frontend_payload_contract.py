# ruff: noqa: E402,I001
"""Check Phase 3-I-H frontend answer strategy payload contract."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DOC_FILE: Final[Path] = (
    PROJECT_ROOT
    / "docs/backend/phase3ih_frontend_answer_strategy_payload_contract_v0.1.md"
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import state_to_response_payload


REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
    "answer_forbidden_fragments",
    "answer_boundary_note_type",
    "answer_strategy_reason",
)

REQUIRED_MODES: Final[tuple[str, ...]] = (
    "single_primary",
    "primary_with_boundary_note",
    "split_required",
    "safety_blocked",
    "handoff_required",
)

REQUIRED_MODULES: Final[tuple[str, ...]] = (
    "spec",
    "price",
    "logistics",
    "quality",
)

FORBIDDEN_FRONTEND_SYNTHESIS: Final[tuple[str, ...]] = (
    "包邮价",
    "保证适配",
    "明天一定到",
    "全网最低",
    "一定赔",
    "一定补发",
    "今天一定发",
    "高质量低价",
)

REQUIRED_DOC_FRAGMENTS: Final[tuple[str, ...]] = (
    "Phase 3-I-H Frontend Answer Strategy Payload Contract v0.1",
    "前端优先读取顶层字段",
    "前端展示优先级",
    "禁止前端行为",
)


def main() -> int:
    """Run frontend payload contract check."""

    print("=" * 80)
    print("checking Phase 3-I-H frontend answer strategy payload contract")

    errors: list[str] = []

    doc_result = check_doc(errors=errors)
    payload_result = check_payload_sample(errors=errors)

    result = {
        "doc_result": doc_result,
        "payload_result": payload_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-H frontend payload contract check failed")
        return 1

    print("Phase 3-I-H frontend payload contract check passed")
    return 0


def check_doc(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check contract document content."""

    if not DOC_FILE.exists():
        errors.append(f"missing contract doc: {DOC_FILE}")
        return {"doc_file": str(DOC_FILE), "exists": False}

    content = DOC_FILE.read_text(encoding="utf-8")
    missing_fragments: list[str] = []

    for fragment in REQUIRED_DOC_FRAGMENTS:
        if fragment not in content:
            missing_fragments.append(fragment)
            errors.append(f"contract doc missing fragment: {fragment}")

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in content
    ]
    missing_modes = [
        mode
        for mode in REQUIRED_MODES
        if mode not in content
    ]
    missing_modules = [
        module
        for module in REQUIRED_MODULES
        if module not in content
    ]
    missing_forbidden = [
        fragment
        for fragment in FORBIDDEN_FRONTEND_SYNTHESIS
        if fragment not in content
    ]

    if missing_fields:
        errors.append(f"contract doc missing fields: {missing_fields}")

    if missing_modes:
        errors.append(f"contract doc missing modes: {missing_modes}")

    if missing_modules:
        errors.append(f"contract doc missing modules: {missing_modules}")

    if missing_forbidden:
        errors.append(
            f"contract doc missing forbidden synthesis fragments: {missing_forbidden}"
        )

    return {
        "doc_file": str(DOC_FILE),
        "exists": True,
        "missing_fragments": missing_fragments,
        "missing_fields": missing_fields,
        "missing_modes": missing_modes,
        "missing_modules": missing_modules,
        "missing_forbidden": missing_forbidden,
    }


def check_payload_sample(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check payload sample matches frontend contract."""

    sample_state: dict[str, Any] = {
        "session_id": "phase3ih-h4-session",
        "conversation_id": "phase3ih-h4-conversation",
        "user_text": "SKU001多少钱，螺纹是什么规格？",
        "final_response": "这类问题涉及报价，需要人工确认。",
        "answer_text": "这类问题涉及报价，需要人工确认。",
        "selected_module": "price",
        "intent": "price",
        "candidate_modules": ["price", "spec"],
        "handoff_required": False,
        "human_handoff": False,
        "response_sources": [],
        "response_warnings": [],
        "risk_flags": [],
        "metadata": {
            "answer_strategy_mode": "primary_with_boundary_note",
            "answer_primary_module": "price",
            "answer_candidate_modules": ["price", "spec"],
            "answer_boundary_notes": [
                "规格信息只能作为补充参考，不能替代正式报价或人工确认。"
            ],
            "answer_split_required": False,
            "answer_handoff_required": False,
            "answer_safety_blocked": False,
            "answer_forbidden_commitment_detected": False,
            "answer_forbidden_fragments": [],
            "answer_boundary_note_type": "price_spec_boundary",
            "answer_strategy_reason": "matched configured module pair rule",
        },
    }

    payload = state_to_response_payload(cast(Any, sample_state))
    metadata = payload.get("metadata")

    if not isinstance(metadata, dict):
        errors.append("payload metadata must be dict")
        metadata = {}

    missing_top_level = [
        field
        for field in REQUIRED_FIELDS
        if field not in payload
    ]
    missing_metadata = [
        field
        for field in REQUIRED_FIELDS
        if field not in metadata
    ]

    if missing_top_level:
        errors.append(f"payload missing top-level fields: {missing_top_level}")

    if missing_metadata:
        errors.append(f"payload missing metadata fields: {missing_metadata}")

    if payload.get("answer_strategy_mode") != "primary_with_boundary_note":
        errors.append("payload answer_strategy_mode mismatch")

    if payload.get("answer_primary_module") != "price":
        errors.append("payload answer_primary_module mismatch")

    if payload.get("answer_candidate_modules") != ["price", "spec"]:
        errors.append("payload answer_candidate_modules mismatch")

    boundary_notes = payload.get("answer_boundary_notes")

    if not isinstance(boundary_notes, list) or not boundary_notes:
        errors.append("payload answer_boundary_notes must be non-empty list")

    return {
        "payload_keys": sorted(payload),
        "metadata_keys": sorted(metadata),
        "missing_top_level": missing_top_level,
        "missing_metadata": missing_metadata,
        "answer_strategy_mode": payload.get("answer_strategy_mode"),
        "answer_primary_module": payload.get("answer_primary_module"),
        "answer_candidate_modules": payload.get("answer_candidate_modules"),
        "answer_boundary_notes": payload.get("answer_boundary_notes"),
    }


if __name__ == "__main__":
    raise SystemExit(main())