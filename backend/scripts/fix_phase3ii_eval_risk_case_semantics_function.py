"""Fix Phase 3-I-I evaluator is_risk_case function semantics."""

from __future__ import annotations

import re
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_SCRIPT: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


NEW_FUNCTION: Final[str] = '''def is_risk_case(
    *,
    scenario_type: str,
    expected_handoff: bool,
    is_critical: bool,
) -> bool:
    """Return whether case should trigger risk gate.

    `is_critical` marks answer correctness severity. It must not by itself
    require handoff or safety blocking.
    """

    _ = is_critical

    return scenario_type == "risk" or expected_handoff
'''


def main() -> int:
    """Fix evaluator risk case semantics function."""

    print("=" * 80)
    print("fixing Phase 3-I-I evaluator is_risk_case function semantics")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_SCRIPT.exists():
        errors.append(f"missing eval script: {EVAL_SCRIPT}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_SCRIPT.read_text(encoding="utf-8")
    original = content

    pattern = re.compile(
        r"def is_risk_case\(\n"
        r".*?"
        r"\n(?=def clean_text\(|def split_semicolon_text\(|def as_text_list\(|\Z)",
        flags=re.DOTALL,
    )

    match = pattern.search(content)

    if match is None:
        errors.append("is_risk_case function block not found")
    else:
        content = content[: match.start()] + NEW_FUNCTION + "\n\n" + content[match.end() :]
        changes.append("replaced is_risk_case function with expected_handoff semantics")

    if "expected_handoff=expected_handoff" not in content:
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
            changes.append("patched is_risk_case call")
        else:
            errors.append("is_risk_case call not patched and old call anchor not found")
    else:
        changes.append("is_risk_case call already passes expected_handoff")

    if "return scenario_type == \"risk\" or is_critical" in content:
        errors.append("old is_critical risk semantics still present")

    if "return scenario_type == \"risk\" or expected_handoff" not in content:
        errors.append("new expected_handoff risk semantics not present")

    if content != original and not errors:
        EVAL_SCRIPT.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator is_risk_case function fix failed")
        return 1

    print("Phase 3-I-I evaluator is_risk_case function fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())