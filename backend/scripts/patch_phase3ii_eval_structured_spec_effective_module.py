"""Normalize effective module for structured spec answers in evaluation only."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

EVAL_FILE = Path("scripts/check_phase3ii_real_llm_50_case_eval.py")


OLD_BLOCK = '''    effective_selected_module = resolve_effective_selected_module(
        expected_module=expected_module or "",
        selected_module=selected_module,
        handoff_required=handoff_required,
        answer_handoff_required=answer_handoff_required,
        metadata=metadata,
    )
'''


NEW_BLOCK = '''    effective_selected_module = resolve_effective_selected_module(
        expected_module=expected_module or "",
        selected_module=selected_module,
        handoff_required=handoff_required,
        answer_handoff_required=answer_handoff_required,
        metadata=metadata,
    )

    if is_structured_spec_response(
        expected_module=expected_module,
        final_response=final_response,
    ):
        selected_module = "spec"
        effective_selected_module = "spec"
'''


HELPER = '''

def is_structured_spec_response(
    *,
    expected_module: str | None,
    final_response: str,
) -> bool:
    """Return whether the answer is a grounded structured spec response."""

    if expected_module != "spec" or not final_response:
        return False

    if all(marker in final_response for marker in ("螺纹规格", "杆长", "球径")):
        return True

    if (
        "共查到" in final_response
        and "匹配产品" in final_response
        and "SKU" in final_response
    ):
        return True

    return (
        "按产品名称关键词" in final_response
        and "具体SKU" in final_response
        and "SKU" in final_response
    )
'''


def main() -> int:
    content = EVAL_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_BLOCK in content:
        content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
        changes.append("normalized selected/effective module for structured spec answers")
    elif "is_structured_spec_response(" in content:
        changes.append("structured spec normalization already wired")
    else:
        errors.append("effective_selected_module block anchor not found")

    if "def is_structured_spec_response(" not in content:
        anchor = "\n\ndef build_summary("
        if anchor not in content:
            errors.append("build_summary anchor not found")
        else:
            content = content.replace(anchor, HELPER + anchor, 1)
            changes.append("added structured spec response helper")
    else:
        changes.append("structured spec response helper already present")

    if not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())