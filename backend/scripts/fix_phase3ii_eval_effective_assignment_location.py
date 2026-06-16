"""Move effective_selected_module assignment to the correct evaluator location."""

from __future__ import annotations

import re
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


ASSIGNMENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"    effective_selected_module = resolve_effective_selected_module\(\n"
    r"        expected_module=expected_module,\n"
    r"        selected_module=selected_module,\n"
    r"        handoff_required=handoff_required,\n"
    r"        answer_handoff_required=answer_handoff_required,\n"
    r"        metadata=metadata,\n"
    r"    \)\n\n"
)


ASSIGNMENT_BLOCK: Final[str] = '''    effective_selected_module = resolve_effective_selected_module(
        expected_module=expected_module or "",
        selected_module=selected_module,
        handoff_required=handoff_required,
        answer_handoff_required=answer_handoff_required,
        metadata=metadata,
    )

'''


MISMATCH_ANCHOR: Final[str] = (
    "    if expected_module and effective_selected_module != expected_module:\n"
)


def main() -> int:
    """Move effective assignment."""

    print("=" * 80)
    print("fixing Phase 3-I-I evaluator effective assignment location")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    content, removed_count = ASSIGNMENT_PATTERN.subn("", content)

    if removed_count:
        changes.append(f"removed misplaced effective assignment block(s): {removed_count}")
    else:
        changes.append("no old effective assignment block found")

    if MISMATCH_ANCHOR not in content:
        errors.append("effective mismatch anchor not found")
    else:
        content = content.replace(
            MISMATCH_ANCHOR,
            ASSIGNMENT_BLOCK + MISMATCH_ANCHOR,
            1,
        )
        changes.append("inserted effective assignment before mismatch check")

    if content != original and not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator effective assignment location fix failed")
        return 1

    print("Phase 3-I-I evaluator effective assignment location fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())