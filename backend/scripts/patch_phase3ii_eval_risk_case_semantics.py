"""Patch Phase 3-I-I evaluator risk case semantics."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_SCRIPT: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


def main() -> int:
    """Patch evaluator risk gate semantics."""

    print("=" * 80)
    print("patching Phase 3-I-I evaluator risk case semantics")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_SCRIPT.exists():
        errors.append(f"missing eval script: {EVAL_SCRIPT}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_SCRIPT.read_text(encoding="utf-8")
    original = content

    old_call = (
        "    if is_risk_case(scenario_type=scenario_type, is_critical=is_critical):\n"
    )
    new_call = (
        "    if is_risk_case(\n"
        "        scenario_type=scenario_type,\n"
        "        expected_handoff=expected_handoff,\n"
        "        is_critical=is_critical,\n"
        "    ):\n"
    )

    if old_call in content:
        content = content.replace(old_call, new_call, 1)
        changes.append("updated is_risk_case call to include expected_handoff")
    elif "expected_handoff=expected_handoff" in content:
        changes.append("is_risk_case call already patched")
    else:
        errors.append("is_risk_case call anchor not found")

    old_function = (
        "def is_risk_case(\n"
        "    *,\n"
        "    scenario_type: str,\n"
        "    is_critical: bool,\n"
        ") -> bool:\n"
        "    \"\"\"Return whether case should trigger risk gate.\"\"\"\n"
        "\n"
        "    return scenario_type == \"risk\" or is_critical\n"
    )

    new_function = (
        "def is_risk_case(\n"
        "    *,\n"
        "    scenario_type: str,\n"
        "    expected_handoff: bool,\n"
        "    is_critical: bool,\n"
        ") -> bool:\n"
        "    \"\"\"Return whether case should trigger risk gate.\n"
        "\n"
        "    `is_critical` marks answer correctness severity. It must not by itself\n"
        "    require handoff or safety blocking.\n"
        "    \"\"\"\n"
        "\n"
        "    _ = is_critical\n"
        "\n"
        "    return scenario_type == \"risk\" or expected_handoff\n"
    )

    if old_function in content:
        content = content.replace(old_function, new_function, 1)
        changes.append("updated is_risk_case semantics")
    elif "return scenario_type == \"risk\" or expected_handoff" in content:
        changes.append("is_risk_case function already patched")
    else:
        errors.append("is_risk_case function anchor not found")

    if content != original:
        EVAL_SCRIPT.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator risk case semantics patch failed")
        return 1

    print("Phase 3-I-I evaluator risk case semantics patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())