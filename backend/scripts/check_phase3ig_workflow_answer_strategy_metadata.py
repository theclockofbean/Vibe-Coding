# ruff: noqa: E402,I001
"""Check Workflow answer strategy metadata integration."""

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

from app.agent.workflow import _apply_answer_strategy_metadata
from app.agent.workflow import _apply_unified_kb_routing


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
    """Run workflow answer strategy metadata check."""

    print("=" * 80)
    print("checking Workflow answer strategy metadata integration")

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
        print("Workflow answer strategy metadata integration check failed")
        return 1

    print("Workflow answer strategy metadata integration check passed")
    return 0


def validate_case(
    *,
    case: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one workflow answer strategy metadata case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = str(case["expected_module"])
    expected_mode = EXPECTED_MODES[case_id]

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

    if final_state.get("selected_module") != expected_module:
        case_errors.append(
            f"selected_module expected {expected_module}, "
            f"got {final_state.get('selected_module')}"
        )

    if metadata.get("answer_strategy_mode") != expected_mode:
        case_errors.append(
            f"answer_strategy_mode expected {expected_mode}, "
            f"got {metadata.get('answer_strategy_mode')}"
        )

    if metadata.get("answer_primary_module") != expected_module:
        case_errors.append("answer_primary_module mismatch")

    candidate_modules = metadata.get("answer_candidate_modules")

    if not isinstance(candidate_modules, list) or expected_module not in candidate_modules:
        case_errors.append("answer_candidate_modules invalid")

    missing_metadata_keys = REQUIRED_METADATA_KEYS - set(metadata)

    if missing_metadata_keys:
        case_errors.append(f"missing metadata keys: {sorted(missing_metadata_keys)}")

    if expected_mode == "safety_blocked":
        if metadata.get("answer_safety_blocked") is not True:
            case_errors.append("answer_safety_blocked must be true")

        if metadata.get("answer_handoff_required") is not True:
            case_errors.append("answer_handoff_required must be true")

    if expected_mode == "primary_with_boundary_note":
        boundary_notes = metadata.get("answer_boundary_notes")

        if not isinstance(boundary_notes, list) or not boundary_notes:
            case_errors.append("answer_boundary_notes must be non-empty list")

        if metadata.get("answer_safety_blocked") is True:
            case_errors.append("primary_with_boundary_note must not be safety blocked")

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": final_state.get("selected_module"),
        "expected_mode": expected_mode,
        "answer_strategy_mode": metadata.get("answer_strategy_mode"),
        "answer_primary_module": metadata.get("answer_primary_module"),
        "answer_candidate_modules": metadata.get("answer_candidate_modules"),
        "answer_boundary_notes": metadata.get("answer_boundary_notes"),
        "answer_safety_blocked": metadata.get("answer_safety_blocked"),
        "answer_handoff_required": metadata.get("answer_handoff_required"),
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())