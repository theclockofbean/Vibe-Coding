# ruff: noqa: E402,I001
"""Check Phase 3-I-G current multi-module answer baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"
ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routing/unified_kb_router.py"
CONFLICT_CASES_JSON: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.json"
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.routing.unified_kb_router import route_query_to_kb


REQUIRED_WORKFLOW_FRAGMENTS: Final[tuple[str, ...]] = (
    "_apply_unified_kb_routing",
    "unified_kb_router_used",
    "unified_kb_candidate_modules",
    "routing_conflict_type",
    "routing_risk_tags",
)

REQUIRED_ROUTER_FRAGMENTS: Final[tuple[str, ...]] = (
    "KBRoutingDecision",
    "route_query_to_kb",
    "candidate_modules",
    "conflict_type",
    "risk_tags",
)

EXPECTED_CASE_COUNT: Final[int] = 15


def main() -> int:
    """Run multi-module answer baseline check."""

    print("=" * 80)
    print("checking Phase 3-I-G multi-module answer baseline")

    errors: list[str] = []

    workflow_result = check_file_fragments(
        path=WORKFLOW_FILE,
        required_fragments=REQUIRED_WORKFLOW_FRAGMENTS,
        errors=errors,
    )
    router_result = check_file_fragments(
        path=ROUTER_FILE,
        required_fragments=REQUIRED_ROUTER_FRAGMENTS,
        errors=errors,
    )
    conflict_result = check_conflict_cases(errors=errors)

    result = {
        "workflow_result": workflow_result,
        "router_result": router_result,
        "conflict_result": conflict_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-G multi-module answer baseline check failed")
        return 1

    print("Phase 3-I-G multi-module answer baseline check passed")
    return 0


def check_file_fragments(
    *,
    path: Path,
    required_fragments: tuple[str, ...],
    errors: list[str],
) -> dict[str, Any]:
    """Check required fragments in one file."""

    if not path.exists():
        errors.append(f"missing file: {path}")
        return {"path": str(path), "exists": False}

    content = path.read_text(encoding="utf-8")
    missing: list[str] = []

    for fragment in required_fragments:
        if fragment not in content:
            missing.append(fragment)
            errors.append(f"{path.name}: missing fragment: {fragment}")

    return {
        "path": str(path),
        "exists": True,
        "required_count": len(required_fragments),
        "missing": missing,
    }


def check_conflict_cases(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check conflict cases and current router behavior."""

    if not CONFLICT_CASES_JSON.exists():
        errors.append(f"missing JSON file: {CONFLICT_CASES_JSON}")
        return {"path": str(CONFLICT_CASES_JSON), "exists": False}

    data = json.loads(CONFLICT_CASES_JSON.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        errors.append("conflict cases JSON root must be object")
        return {"path": str(CONFLICT_CASES_JSON), "exists": True}

    cases = cast(list[dict[str, Any]], data.get("cases", []))

    if len(cases) != EXPECTED_CASE_COUNT:
        errors.append(f"expected {EXPECTED_CASE_COUNT} cases, got {len(cases)}")

    multi_module_cases: list[dict[str, Any]] = []

    for case in cases:
        query = str(case.get("query", ""))
        decision = route_query_to_kb(query)

        if len(decision.candidate_modules) < 2:
            errors.append(
                f"{case.get('case_id')}: expected at least two candidate modules, "
                f"got {decision.candidate_modules}"
            )

        multi_module_cases.append(
            {
                "case_id": case.get("case_id"),
                "expected_module": case.get("expected_module"),
                "selected_module": decision.selected_module,
                "candidate_modules": decision.candidate_modules,
                "conflict_type": decision.conflict_type,
                "risk_tags": decision.risk_tags,
            }
        )

    return {
        "path": str(CONFLICT_CASES_JSON),
        "exists": True,
        "case_count": len(cases),
        "multi_module_case_count": len(multi_module_cases),
        "sample": multi_module_cases[:5],
    }


if __name__ == "__main__":
    raise SystemExit(main())