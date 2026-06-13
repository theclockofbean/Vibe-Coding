# ruff: noqa: E402,I001
"""Check Phase 3-I-F unified KB router helper."""

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

from app.agent.routing.unified_kb_router import route_query_to_kb


JSON_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.json"
)


def main() -> int:
    """Run unified KB router check."""

    print("=" * 80)
    print("checking Phase 3-I-F unified KB router")

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
        "passed_count": len(cases) - len(errors),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }

    pprint(summary)

    if errors:
        print("Phase 3-I-F unified KB router check failed")
        return 1

    print("Phase 3-I-F unified KB router check passed")
    return 0


def validate_case(
    *,
    case: dict[str, Any],
    module_collections: dict[str, str],
    module_sources: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one conflict case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = str(case["expected_module"])
    expected_conflict_type = str(case["conflict_type"])

    decision = route_query_to_kb(query)
    metadata = decision.to_metadata()

    case_errors: list[str] = []

    if decision.selected_module != expected_module:
        case_errors.append(
            f"selected_module expected {expected_module}, "
            f"got {decision.selected_module}"
        )

    if decision.conflict_type != expected_conflict_type:
        case_errors.append(
            f"conflict_type expected {expected_conflict_type}, "
            f"got {decision.conflict_type}"
        )

    if metadata.get("retrieval_selected_module") != expected_module:
        case_errors.append("metadata retrieval_selected_module mismatch")

    if metadata.get("retrieval_source") != module_sources[expected_module]:
        case_errors.append("metadata retrieval_source mismatch")

    if (
        metadata.get("retrieval_collection_name")
        != module_collections[expected_module]
    ):
        case_errors.append("metadata retrieval_collection_name mismatch")

    if "retrieval_hit_count" not in metadata:
        case_errors.append("metadata retrieval_hit_count missing")

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": decision.selected_module,
        "expected_conflict_type": expected_conflict_type,
        "conflict_type": decision.conflict_type,
        "candidate_modules": decision.candidate_modules,
        "matched_signals": decision.matched_signals,
        "reason": decision.reason,
        "risk_tags": decision.risk_tags,
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())