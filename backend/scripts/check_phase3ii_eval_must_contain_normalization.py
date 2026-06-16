# ruff: noqa: E402,I001
"""Check evaluator must-contain numeric normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from pprint import pprint
from typing import Final, Protocol


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


class EvalModuleProtocol(Protocol):
    """Protocol for evaluator helper functions."""

    def contains_required_fragment(
        self,
        final_response: str,
        fragment: str,
    ) -> bool:
        """Return whether required fragment is contained."""

    def contains_any_required_fragment(
        self,
        final_response: str,
        fragments: list[str],
    ) -> bool:
        """Return whether any required fragment is contained."""


def main() -> int:
    """Run normalization checks."""

    print("=" * 80)
    print("checking Phase 3-I-I evaluator must-contain normalization")

    errors: list[str] = []
    module = load_eval_module()

    checks = [
        {
            "name": "40mm_matches_40_00_mm",
            "actual": module.contains_required_fragment("杆长 40.00 mm", "40mm"),
            "expected": True,
        },
        {
            "name": "55mm_matches_55_00_mm",
            "actual": module.contains_required_fragment("杆长 55.00 mm", "55mm"),
            "expected": True,
        },
        {
            "name": "45mm_matches_45_00_mm",
            "actual": module.contains_required_fragment("球径 45.00 mm", "45mm"),
            "expected": True,
        },
        {
            "name": "62mm_matches_62_00_mm",
            "actual": module.contains_required_fragment("球径 62.00 mm", "62mm"),
            "expected": True,
        },
        {
            "name": "75_any_matches_75_00_mm",
            "actual": module.contains_any_required_fragment("杆长 75.00 mm", ["75"]),
            "expected": True,
        },
        {
            "name": "plain_exact_still_works",
            "actual": module.contains_required_fragment("SKU004 M10×1.5", "SKU004"),
            "expected": True,
        },
        {
            "name": "negative_still_false",
            "actual": module.contains_required_fragment("杆长 40.00 mm", "75mm"),
            "expected": False,
        },
    ]

    for item in checks:
        if item["actual"] != item["expected"]:
            errors.append(
                f"{item['name']}: expected {item['expected']}, got {item['actual']}"
            )

    pprint({"checks": checks, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator must-contain normalization check failed")
        return 1

    print("Phase 3-I-I evaluator must-contain normalization check passed")
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