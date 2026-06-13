# ruff: noqa: E402,I001
"""Check Phase 3-I-G answer strategy helper."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.answering.multimodule_answer_strategy import decide_answer_strategy
from app.agent.routing.unified_kb_router import route_query_to_kb


CONFLICT_CASES_JSON: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.json"
)

EXPECTED_MODES: Final[dict[str, str]] = {
    "CONFLICT_001": "primary_with_boundary_note",
    "CONFLICT_002": "primary_with_boundary_note",
    "CONFLICT_003": "primary_with_boundary_note",
    "CONFLICT_004": "safety_blocked",
    "CONFLICT_005": "safety_blocked",
    "CONFLICT_006": "primary_with_boundary_note",
    "CONFLICT_007": "primary_with_boundary_note",
    "CONFLICT_008": "primary_with_boundary_note",
    "CONFLICT_009": "safety_blocked",
    "CONFLICT_010": "safety_blocked",
    "CONFLICT_011": "primary_with_boundary_note",
    "CONFLICT_012": "safety_blocked",
    "CONFLICT_013": "primary_with_boundary_note",
    "CONFLICT_014": "primary_with_boundary_note",
    "CONFLICT_015": "safety_blocked",
}

REQUIRED_METADATA_KEYS: Final[set[str]] = {
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
}


def main() -> int:
    """Run answer strategy helper check."""

    print("=" * 80)
    print("checking Phase 3-I-G answer strategy helper")

    errors: list[str] = []

    if not CONFLICT_CASES_JSON.exists():
        errors.append(f"missing JSON file: {CONFLICT_CASES_JSON}")
        pprint({"errors": errors})
        return 1

    data = json.loads(CONFLICT_CASES_JSON.read_text(encoding="utf-8"))
    cases = cast(list[dict[str, Any]], data.get("cases", []))

    results: list[dict[str, Any]] = []

    for case in cases:
        result = validate_case(case=case, errors=errors)
        results.append(result)

    summary = {
        "case_count": len(cases),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }

    pprint(summary)

    if errors:
        print("Phase 3-I-G answer strategy helper check failed")
        return 1

    print("Phase 3-I-G answer strategy helper check passed")
    return 0


def validate_case(
    *,
    case: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one routed conflict case through answer strategy helper."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = str(case["expected_module"])
    expected_mode = EXPECTED_MODES[case_id]

    routing_decision = route_query_to_kb(query)
    strategy_decision = decide_answer_strategy(
        query=query,
        selected_module=routing_decision.selected_module,
        candidate_modules=routing_decision.candidate_modules,
        conflict_type=routing_decision.conflict_type,
    )
    metadata = strategy_decision.to_metadata()
    case_errors: list[str] = []

    if routing_decision.selected_module != expected_module:
        case_errors.append(
            f"routing selected_module expected {expected_module}, "
            f"got {routing_decision.selected_module}"
        )

    if strategy_decision.strategy_mode != expected_mode:
        case_errors.append(
            f"strategy_mode expected {expected_mode}, "
            f"got {strategy_decision.strategy_mode}"
        )

    if strategy_decision.primary_module != expected_module:
        case_errors.append(
            f"primary_module expected {expected_module}, "
            f"got {strategy_decision.primary_module}"
        )

    missing_metadata_keys = REQUIRED_METADATA_KEYS - set(metadata)

    if missing_metadata_keys:
        case_errors.append(f"missing metadata keys: {sorted(missing_metadata_keys)}")

    if metadata.get("answer_strategy_mode") != expected_mode:
        case_errors.append("metadata answer_strategy_mode mismatch")

    if metadata.get("answer_primary_module") != expected_module:
        case_errors.append("metadata answer_primary_module mismatch")

    if expected_mode == "safety_blocked":
        if strategy_decision.handoff_required is not True:
            case_errors.append("safety_blocked must require handoff")

        if strategy_decision.safety_blocked is not True:
            case_errors.append("safety_blocked flag must be true")

    if expected_mode == "primary_with_boundary_note":
        if not strategy_decision.boundary_notes:
            case_errors.append("primary_with_boundary_note must include boundary note")

        if strategy_decision.safety_blocked is True:
            case_errors.append("primary_with_boundary_note must not be safety_blocked")

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": routing_decision.selected_module,
        "candidate_modules": routing_decision.candidate_modules,
        "conflict_type": routing_decision.conflict_type,
        "expected_mode": expected_mode,
        "strategy_mode": strategy_decision.strategy_mode,
        "boundary_note_type": strategy_decision.boundary_note_type,
        "boundary_notes": strategy_decision.boundary_notes,
        "forbidden_fragments": strategy_decision.forbidden_fragments,
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())