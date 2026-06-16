# ruff: noqa: E402,I001
"""Check Phase 3-I-I evaluator effective escalation module helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from pprint import pprint
from typing import Any, Final, Protocol


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


class EvalModuleProtocol(Protocol):
    """Protocol for evaluator module."""

    def resolve_effective_selected_module(
        self,
        *,
        expected_module: str,
        selected_module: object,
        handoff_required: bool,
        answer_handoff_required: bool,
        metadata: dict[str, object],
    ) -> str | None:
        """Resolve effective selected module."""


def main() -> int:
    """Run effective escalation module check."""

    print("=" * 80)
    print("checking Phase 3-I-I evaluator effective escalation module")

    errors: list[str] = []

    module = load_eval_module()

    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "escalation_general_with_handoff",
            "actual": module.resolve_effective_selected_module(
                expected_module="escalation",
                selected_module="general",
                handoff_required=True,
                answer_handoff_required=False,
                metadata={"llm_intent": "escalation"},
            ),
            "expected": "escalation",
        }
    )

    checks.append(
        {
            "name": "escalation_general_with_priority_recheck",
            "actual": module.resolve_effective_selected_module(
                expected_module="escalation",
                selected_module="general",
                handoff_required=False,
                answer_handoff_required=True,
                metadata={
                    "phase3ii_priority_local_recheck_intent": "escalation",
                },
            ),
            "expected": "escalation",
        }
    )

    checks.append(
        {
            "name": "spec_unchanged",
            "actual": module.resolve_effective_selected_module(
                expected_module="spec",
                selected_module="spec",
                handoff_required=False,
                answer_handoff_required=False,
                metadata={"llm_intent": "spec"},
            ),
            "expected": "spec",
        }
    )

    checks.append(
        {
            "name": "escalation_without_handoff_not_effective",
            "actual": module.resolve_effective_selected_module(
                expected_module="escalation",
                selected_module="general",
                handoff_required=False,
                answer_handoff_required=False,
                metadata={"llm_intent": "escalation"},
            ),
            "expected": "general",
        }
    )

    for item in checks:
        if item["actual"] != item["expected"]:
            errors.append(
                f"{item['name']}: expected {item['expected']}, got {item['actual']}"
            )

    pprint({"checks": checks, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator effective escalation module check failed")
        return 1

    print("Phase 3-I-I evaluator effective escalation module check passed")
    return 0


def load_eval_module() -> EvalModuleProtocol:
    """Load evaluator script as module."""

    spec = importlib.util.spec_from_file_location(
        "phase3ii_real_llm_eval_module",
        EVAL_FILE,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


if __name__ == "__main__":
    raise SystemExit(main())