# ruff: noqa: E402,I001
"""Check Phase 3-I-G renderer answer strategy gate design."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DOC_FILE: Final[Path] = (
    PROJECT_ROOT
    / "docs/backend/phase3ig_renderer_answer_strategy_gate_design_v0.1.md"
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.workflow import _apply_answer_strategy_metadata
from app.agent.workflow import _apply_unified_kb_routing


REQUIRED_DOC_FRAGMENTS: Final[tuple[str, ...]] = (
    "Phase 3-I-G Renderer Answer Strategy Gate Design v0.1",
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
    "single_primary",
    "primary_with_boundary_note",
    "split_required",
    "safety_blocked",
    "handoff_required",
    "Answer Strategy metadata 不是事实来源",
)

FORBIDDEN_FUSION_FRAGMENTS: Final[tuple[str, ...]] = (
    "包邮价",
    "适配后马上发",
    "高质量低价",
    "保证适配且质量没问题",
    "今天一定发",
    "明天一定到",
    "一定赔",
    "一定补发",
    "最低价给你",
    "全网最低",
)

REQUIRED_METADATA_KEYS: Final[set[str]] = {
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
}

SAMPLE_CASES: Final[tuple[dict[str, str], ...]] = (
    {
        "case_id": "GATE_001",
        "query": "SKU001多少钱，螺纹是什么规格？",
        "expected_mode": "primary_with_boundary_note",
        "expected_module": "price",
    },
    {
        "case_id": "GATE_002",
        "query": "便宜点能包邮吗？",
        "expected_mode": "safety_blocked",
        "expected_module": "price",
    },
    {
        "case_id": "GATE_003",
        "query": "这个保证适配并且明天到吗？",
        "expected_mode": "safety_blocked",
        "expected_module": "spec",
    },
)


def main() -> int:
    """Run renderer gate design check."""

    print("=" * 80)
    print("checking Phase 3-I-G renderer answer strategy gate design")

    errors: list[str] = []

    doc_result = check_doc(errors=errors)
    metadata_result = check_workflow_metadata(errors=errors)

    result = {
        "doc_result": doc_result,
        "metadata_result": metadata_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-G renderer answer strategy gate design check failed")
        return 1

    print("Phase 3-I-G renderer answer strategy gate design check passed")
    return 0


def check_doc(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check renderer gate design doc."""

    if not DOC_FILE.exists():
        errors.append(f"missing doc file: {DOC_FILE}")
        return {"doc_file": str(DOC_FILE), "exists": False}

    content = DOC_FILE.read_text(encoding="utf-8")
    missing_required: list[str] = []
    missing_forbidden: list[str] = []

    for fragment in REQUIRED_DOC_FRAGMENTS:
        if fragment not in content:
            missing_required.append(fragment)
            errors.append(f"doc missing required fragment: {fragment}")

    for fragment in FORBIDDEN_FUSION_FRAGMENTS:
        if fragment not in content:
            missing_forbidden.append(fragment)
            errors.append(f"doc missing forbidden fusion fragment: {fragment}")

    return {
        "doc_file": str(DOC_FILE),
        "exists": True,
        "required_count": len(REQUIRED_DOC_FRAGMENTS),
        "forbidden_fusion_count": len(FORBIDDEN_FUSION_FRAGMENTS),
        "missing_required": missing_required,
        "missing_forbidden": missing_forbidden,
    }


def check_workflow_metadata(
    *,
    errors: list[str],
) -> list[dict[str, Any]]:
    """Check Workflow already produces metadata needed by renderer gate."""

    results: list[dict[str, Any]] = []

    for case in SAMPLE_CASES:
        result = validate_case(case=case, errors=errors)
        results.append(result)

    return results


def validate_case(
    *,
    case: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one sample case."""

    case_id = case["case_id"]
    query = case["query"]
    expected_mode = case["expected_mode"]
    expected_module = case["expected_module"]

    state = {
        "user_text": query,
        "current_message": query,
        "query": query,
        "metadata": {},
        "retrieved_chunks": [],
    }

    routed_state = _apply_unified_kb_routing(cast(Any, state))
    final_state = cast(
        dict[str, Any],
        _apply_answer_strategy_metadata(routed_state),
    )
    metadata = cast(dict[str, Any], final_state.get("metadata") or {})
    case_errors: list[str] = []

    missing_metadata = REQUIRED_METADATA_KEYS - set(metadata)

    if missing_metadata:
        case_errors.append(f"missing metadata keys: {sorted(missing_metadata)}")

    if metadata.get("answer_strategy_mode") != expected_mode:
        case_errors.append(
            f"answer_strategy_mode expected {expected_mode}, "
            f"got {metadata.get('answer_strategy_mode')}"
        )

    if metadata.get("answer_primary_module") != expected_module:
        case_errors.append(
            f"answer_primary_module expected {expected_module}, "
            f"got {metadata.get('answer_primary_module')}"
        )

    if expected_mode == "safety_blocked":
        if metadata.get("answer_safety_blocked") is not True:
            case_errors.append("answer_safety_blocked must be true")

        if metadata.get("answer_handoff_required") is not True:
            case_errors.append("answer_handoff_required must be true")

    if expected_mode == "primary_with_boundary_note":
        boundary_notes = metadata.get("answer_boundary_notes")

        if not isinstance(boundary_notes, list) or not boundary_notes:
            case_errors.append("answer_boundary_notes must be non-empty list")

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "expected_mode": expected_mode,
        "answer_strategy_mode": metadata.get("answer_strategy_mode"),
        "expected_module": expected_module,
        "answer_primary_module": metadata.get("answer_primary_module"),
        "answer_safety_blocked": metadata.get("answer_safety_blocked"),
        "answer_handoff_required": metadata.get("answer_handoff_required"),
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())