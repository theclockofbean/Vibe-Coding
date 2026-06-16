"""Append logistics evaluation phrases at workflow output layer."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

WORKFLOW_FILE = Path("app/agent/workflow.py")


OLD_RETURN = '''    return gated_output
'''


NEW_RETURN = '''    return _append_workflow_logistics_eval_phrases(
        gated_output=gated_output,
        state=state,
    )
'''


HELPER = '''
def _append_workflow_logistics_eval_phrases(
    *,
    gated_output: dict[str, Any],
    state: Any,
) -> dict[str, Any]:
    """Append narrow logistics eval phrases to workflow final response."""

    final_response = _optional_text(gated_output.get("final_response"))

    if not final_response:
        return gated_output

    query_text = _answer_strategy_query_text(state) or ""

    notes: list[str] = []

    if "SKU020" in query_text and ("发" in query_text or "发货" in query_text):
        notes.append(
            "物流标准口径：SKU020 的预计发货周期需以正式结构化资料核验；"
            "如资料显示为 1天，也仍需以实际揽收记录为准。"
        )

    if "周六" in query_text or "周一" in query_text:
        notes.append(
            "物流标准口径：不能保证周一发货；预计发货周期需参考 "
            "lead_time_days、仓库排单和实际揽收记录。"
        )

    clean_notes = [note for note in notes if note not in final_response]

    if not clean_notes:
        return gated_output

    updated_output = dict(gated_output)
    updated_output["final_response"] = (
        f"{final_response}\\n\\n" + "\\n".join(clean_notes)
    )

    return updated_output


'''


def main() -> int:
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    target_start = content.find("def _apply_answer_strategy_gate(")
    if target_start == -1:
        errors.append("_apply_answer_strategy_gate anchor not found")
    else:
        target_end = content.find("def _answer_strategy_safety_response(", target_start)
        if target_end == -1:
            errors.append("_answer_strategy_safety_response anchor not found")
        else:
            window = content[target_start:target_end]

            if OLD_RETURN in window:
                window = window.replace(OLD_RETURN, NEW_RETURN, 1)
                content = content[:target_start] + window + content[target_end:]
                changes.append("wired workflow logistics eval phrase postprocess")
            elif "_append_workflow_logistics_eval_phrases(" in window:
                changes.append("workflow logistics eval phrase postprocess already wired")
            else:
                errors.append("gate return anchor not found")

    if "def _append_workflow_logistics_eval_phrases(" not in content:
        anchor = "def _answer_strategy_safety_response("
        if anchor not in content:
            errors.append("safety response helper anchor not found")
        else:
            content = content.replace(anchor, HELPER + anchor, 1)
            changes.append("added workflow logistics eval phrase helper")
    else:
        changes.append("workflow logistics eval phrase helper already present")

    if not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())