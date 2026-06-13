# ruff: noqa: E402,I001
"""Check workflow integration with unified KB router."""

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

from app.agent.workflow import _apply_unified_kb_routing


JSON_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.json"
)


def main() -> int:
    """Run workflow unified router integration check."""

    print("=" * 80)
    print("checking workflow unified KB router integration")

    errors: list[str] = []

    if not JSON_FILE.exists():
        errors.append(f"missing JSON file: {JSON_FILE}")
        pprint({"errors": errors})
        return 1

    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    cases = cast(list[dict[str, Any]], data.get("cases", []))
    module_collections = cast(dict[str, str], data.get("module_collections", {}))
    module_sources = cast(dict[str, str], data.get("module_sources", {}))

    results: list[dict[str, Any]] = []

    for case in cases:
        result = validate_case(
            case=case,
            module_collections=module_collections,
            module_sources=module_sources,
            errors=errors,
        )
        results.append(result)

    summary = {
        "case_count": len(cases),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }

    pprint(summary)

    if errors:
        print("workflow unified KB router integration check failed")
        return 1

    print("workflow unified KB router integration check passed")
    return 0


def validate_case(
    *,
    case: dict[str, Any],
    module_collections: dict[str, str],
    module_sources: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one workflow routing case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = str(case["expected_module"])
    expected_conflict_type = str(case["conflict_type"])

    state = {
        "user_text": query,
        "current_message": query,
        "query": query,
        "metadata": {},
        "retrieved_chunks": [],
    }

    new_state = cast(dict[str, Any], _apply_unified_kb_routing(cast(Any, state)))
    metadata = cast(dict[str, Any], new_state.get("metadata") or {})
    case_errors: list[str] = []

    if new_state.get("selected_module") != expected_module:
        case_errors.append(
            f"selected_module expected {expected_module}, "
            f"got {new_state.get('selected_module')}"
        )

    if new_state.get("intent") != expected_module:
        case_errors.append(
            f"intent expected {expected_module}, got {new_state.get('intent')}"
        )

    if expected_module not in cast(list[str], new_state.get("candidate_modules", [])):
        case_errors.append("expected module missing from candidate_modules")

    if metadata.get("unified_kb_router_used") is not True:
        case_errors.append("unified_kb_router_used must be true")

    if metadata.get("unified_kb_selected_module") != expected_module:
        case_errors.append("unified_kb_selected_module mismatch")

    if metadata.get("unified_kb_conflict_type") != expected_conflict_type:
        case_errors.append("unified_kb_conflict_type mismatch")

    expected_source = module_sources[expected_module]
    expected_collection = module_collections[expected_module]

    if expected_source != f"real_{expected_module}_kb":
        case_errors.append("JSON source baseline mismatch")

    if expected_collection != f"{expected_module}_kb_v1":
        case_errors.append("JSON collection baseline mismatch")

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": new_state.get("selected_module"),
        "intent": new_state.get("intent"),
        "candidate_modules": new_state.get("candidate_modules"),
        "expected_conflict_type": expected_conflict_type,
        "unified_kb_conflict_type": metadata.get("unified_kb_conflict_type"),
        "matched_signals": metadata.get("unified_kb_matched_signals"),
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())