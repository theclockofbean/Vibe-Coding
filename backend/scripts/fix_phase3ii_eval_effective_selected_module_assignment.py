"""Fix missing effective_selected_module assignment in evaluator."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


ASSIGNMENT_BLOCK: Final[str] = '''    effective_selected_module = resolve_effective_selected_module(
        expected_module=expected_module,
        selected_module=selected_module,
        handoff_required=handoff_required,
        answer_handoff_required=answer_handoff_required,
        metadata=metadata,
    )

'''


def main() -> int:
    """Insert effective_selected_module assignment and remove unused cast import."""

    print("=" * 80)
    print("fixing Phase 3-I-I evaluator effective_selected_module assignment")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    content = content.replace(
        "from typing import Any, Final, cast\n",
        "from typing import Any, Final\n",
    )
    if content != original:
        changes.append("removed unused cast import")

    if "def resolve_effective_selected_module(" not in content:
        errors.append("resolve_effective_selected_module helper missing")

    if "effective_selected_module = resolve_effective_selected_module(" not in content:
        anchor = "    failure_reasons: list[str] = []\n"

        if anchor not in content:
            errors.append("failure_reasons anchor not found")
        else:
            content = content.replace(anchor, ASSIGNMENT_BLOCK + anchor, 1)
            changes.append("inserted effective_selected_module assignment")
    else:
        changes.append("effective_selected_module assignment already present")

    if content != original and not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator effective_selected_module assignment fix failed")
        return 1

    print("Phase 3-I-I evaluator effective_selected_module assignment fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())