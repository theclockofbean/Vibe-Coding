"""Patch evaluator must-contain matching with numeric normalization."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


HELPER_FUNCTION: Final[str] = '''
def normalize_required_fragment_text(
    value: str,
) -> str:
    """Normalize text for evaluator required-fragment matching.

    This keeps normal exact matching behavior but also lets formatted numeric
    dimensions match across renderer/evaluator style differences, e.g.
    "55.00 mm" satisfies "55mm".
    """

    normalized = value.strip()
    normalized = normalized.replace("　", "")
    normalized = normalized.replace(" ", "")
    normalized = normalized.replace("毫米", "mm")
    normalized = normalized.replace("MM", "mm")
    normalized = normalized.replace("ｍｍ", "mm")
    normalized = normalized.replace("：", ":")
    normalized = normalized.replace("∶", ":")

    normalized = re.sub(r"(?<!\\d)(\\d+)\\.0+mm", r"\\1mm", normalized)

    return normalized


def contains_required_fragment(
    final_response: str,
    fragment: str,
) -> bool:
    """Return whether final response satisfies required fragment."""

    if fragment in final_response:
        return True

    normalized_response = normalize_required_fragment_text(final_response)
    normalized_fragment = normalize_required_fragment_text(fragment)

    if not normalized_fragment:
        return False

    return normalized_fragment in normalized_response


def contains_any_required_fragment(
    final_response: str,
    fragments: list[str],
) -> bool:
    """Return whether final response satisfies any required fragment."""

    return any(
        contains_required_fragment(final_response, fragment)
        for fragment in fragments
    )
'''


OLD_ALL_BLOCK: Final[str] = '''    for fragment in split_semicolon_text(case.get("must_contain_all")):
        if fragment not in final_response:
            failure_reasons.append(
                f"{MAJOR_PREFIX}: missing must_contain_all fragment: {fragment}"
            )
'''


NEW_ALL_BLOCK: Final[str] = '''    for fragment in split_semicolon_text(case.get("must_contain_all")):
        if not contains_required_fragment(final_response, fragment):
            failure_reasons.append(
                f"{MAJOR_PREFIX}: missing must_contain_all fragment: {fragment}"
            )
'''


OLD_ANY_BLOCK: Final[str] = '''    if must_contain_any and not any(fragment in final_response for fragment in must_contain_any):
        failure_reasons.append(
            f"{MAJOR_PREFIX}: missing any of must_contain_any: {must_contain_any}"
        )
'''


NEW_ANY_BLOCK: Final[str] = '''    if must_contain_any and not contains_any_required_fragment(
        final_response,
        must_contain_any,
    ):
        failure_reasons.append(
            f"{MAJOR_PREFIX}: missing any of must_contain_any: {must_contain_any}"
        )
'''


def main() -> int:
    """Patch must-contain matching normalization."""

    print("=" * 80)
    print("patching Phase 3-I-I evaluator must-contain normalization")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    if "def normalize_required_fragment_text(" not in content:
        anchor = "\ndef contains_unsafe_fragment("
        if anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(anchor, HELPER_FUNCTION + "\n" + anchor, 1)
            changes.append("inserted required-fragment normalization helpers")
    else:
        changes.append("required-fragment normalization helpers already present")

    if OLD_ALL_BLOCK in content:
        content = content.replace(OLD_ALL_BLOCK, NEW_ALL_BLOCK, 1)
        changes.append("patched must_contain_all matching")
    elif "contains_required_fragment(final_response, fragment)" in content:
        changes.append("must_contain_all matching already patched")
    else:
        errors.append("must_contain_all matching anchor not found")

    if OLD_ANY_BLOCK in content:
        content = content.replace(OLD_ANY_BLOCK, NEW_ANY_BLOCK, 1)
        changes.append("patched must_contain_any matching")
    elif "contains_any_required_fragment(" in content:
        changes.append("must_contain_any matching already patched")
    else:
        errors.append("must_contain_any matching anchor not found")

    if content != original and not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator must-contain normalization patch failed")
        return 1

    print("Phase 3-I-I evaluator must-contain normalization patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())