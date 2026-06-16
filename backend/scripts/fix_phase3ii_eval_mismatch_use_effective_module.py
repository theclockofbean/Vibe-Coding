"""Fix evaluator mismatch failure reason to use effective_selected_module."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


OLD_BLOCKS: Final[tuple[str, ...]] = (
    '''    if expected_module and selected_module != expected_module:
        failure_reasons.append(
            f"MAJOR: selected_module expected {expected_module}, got {selected_module}"
        )
''',
    '''    if expected_module and selected_module != expected_module:
        failure_reasons.append(
            f"{MAJOR_PREFIX}: selected_module expected {expected_module}, got {selected_module}"
        )
''',
)


NEW_BLOCK: Final[str] = '''    if expected_module and effective_selected_module != expected_module:
        failure_reasons.append(
            f"{MAJOR_PREFIX}: selected_module expected {expected_module}, "
            f"got {selected_module}; effective={effective_selected_module}"
        )
'''


def main() -> int:
    """Patch evaluator mismatch check."""

    print("=" * 80)
    print("fixing Phase 3-I-I evaluator mismatch to use effective module")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    if "effective_selected_module != expected_module" in content:
        changes.append("mismatch check already uses effective_selected_module")
    else:
        replaced = False

        for old_block in OLD_BLOCKS:
            if old_block in content:
                content = content.replace(old_block, NEW_BLOCK, 1)
                changes.append("updated mismatch failure reason to effective module")
                replaced = True
                break

        if not replaced:
            errors.append("mismatch selected_module block not found")

    if '"effective_selected_module": effective_selected_module' not in content:
        old_result_field = '        "selected_module": selected_module,\n'
        new_result_field = (
            '        "selected_module": selected_module,\n'
            '        "effective_selected_module": effective_selected_module,\n'
        )

        if old_result_field in content:
            content = content.replace(old_result_field, new_result_field, 1)
            changes.append("added effective_selected_module to result payload")
        else:
            errors.append("selected_module result field not found")
    else:
        changes.append("effective_selected_module result payload already present")

    if content != original and not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator mismatch effective-module fix failed")
        return 1

    print("Phase 3-I-I evaluator mismatch effective-module fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())