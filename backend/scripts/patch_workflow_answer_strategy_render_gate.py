"""Patch workflow render node with answer strategy gate."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

RENDER_CALL_LINE: Final[str] = (
    "            render_input, render_output = _run_grounded_render_for_state(new_state)"
)

GATE_LINE: Final[str] = (
    "            render_output = _apply_answer_strategy_render_gate(new_state, render_output)"
)

HELPER_BLOCK: Final[str] = '''
def _apply_answer_strategy_render_gate(
    state: AgentState,
    render_output: dict[str, Any],
) -> dict[str, Any]:
    """Apply answer strategy gate to grounded render output."""

    metadata = _ensure_metadata(state)
    gated_output = dict(render_output)
    render_metadata = _as_dict(gated_output.get("metadata"))

    strategy_mode = _optional_text(metadata.get("answer_strategy_mode"))
    boundary_notes = _as_text_list(metadata.get("answer_boundary_notes"))
    safety_blocked = metadata.get("answer_safety_blocked") is True
    handoff_required = metadata.get("answer_handoff_required") is True
    split_required = metadata.get("answer_split_required") is True

    if safety_blocked or handoff_required:
        gated_output["final_response"] = _answer_strategy_safety_response(metadata)
        gated_output["needs_handoff"] = True
        gated_output["is_grounded"] = False
        gated_output["used_llm_output"] = False

        render_metadata["render_mode"] = "answer_strategy_safety_blocked"
        render_metadata["render_safety_blocked"] = True
        render_metadata["render_fallback_reason"] = "answer_strategy_gate"

        gated_output["metadata"] = render_metadata
        gated_output["response_warnings"] = _merge_text_lists(
            _as_text_list(gated_output.get("response_warnings")),
            ["answer strategy safety gate applied"],
        )
        gated_output["risk_flags"] = _merge_text_lists(
            _as_text_list(gated_output.get("risk_flags")),
            ["answer_strategy_safety_blocked"],
        )

        return gated_output

    if split_required:
        gated_output["final_response"] = _answer_strategy_split_response(metadata)
        gated_output["needs_handoff"] = False
        gated_output["is_grounded"] = False
        gated_output["used_llm_output"] = False

        render_metadata["render_mode"] = "answer_strategy_split_required"
        render_metadata["render_safety_blocked"] = False
        render_metadata["render_fallback_reason"] = "answer_strategy_split_required"

        gated_output["metadata"] = render_metadata
        gated_output["response_warnings"] = _merge_text_lists(
            _as_text_list(gated_output.get("response_warnings")),
            ["answer strategy split gate applied"],
        )

        return gated_output

    if strategy_mode == "primary_with_boundary_note" and boundary_notes:
        final_response = _optional_text(gated_output.get("final_response")) or ""

        if final_response:
            gated_output["final_response"] = _append_answer_strategy_boundary_notes(
                final_response=final_response,
                boundary_notes=boundary_notes,
            )

            render_metadata["render_answer_strategy_gate_applied"] = True
            render_metadata["render_answer_strategy_boundary_note_count"] = len(
                boundary_notes
            )
            gated_output["metadata"] = render_metadata

    return gated_output


def _answer_strategy_safety_response(
    metadata: dict[str, Any],
) -> str:
    """Build safety-blocked answer strategy response."""

    forbidden_fragments = _as_text_list(metadata.get("answer_forbidden_fragments"))

    if forbidden_fragments:
        return (
            "该问题涉及高风险业务承诺，不能直接给出确定性答复。"
            "请转人工结合正式数据、业务规则和授权信息确认后再回复。"
        )

    return (
        "该问题涉及需要进一步确认的信息。"
        "为避免给出未经授权的业务承诺，请转人工结合正式数据和业务规则处理。"
    )


def _answer_strategy_split_response(
    metadata: dict[str, Any],
) -> str:
    """Build split-required answer strategy response."""

    candidate_modules = _as_text_list(metadata.get("answer_candidate_modules"))

    if candidate_modules:
        return (
            "识别到多个业务问题："
            + "、".join(candidate_modules)
            + "。当前不自动合并多个模块回答，请拆分为规格、价格、物流或质量中的一个问题后重新提问。"
        )

    return "当前问题包含多个业务方向，请拆分为规格、价格、物流或质量中的一个问题后重新提问。"


def _append_answer_strategy_boundary_notes(
    *,
    final_response: str,
    boundary_notes: list[str],
) -> str:
    """Append answer strategy boundary notes to final response."""

    unique_notes = [
        note
        for note in _deduplicate_text_list(boundary_notes)
        if note and note not in final_response
    ]

    if not unique_notes:
        return final_response

    return final_response.rstrip() + "\\n\\n补充边界：" + "；".join(unique_notes)
'''


def main() -> int:
    """Patch workflow render gate."""

    print("=" * 80)
    print("patching workflow.py answer strategy render gate")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    if GATE_LINE not in content:
        if RENDER_CALL_LINE not in content:
            pprint({"error": "render call anchor not found"})
            return 1

        content = content.replace(
            RENDER_CALL_LINE,
            RENDER_CALL_LINE + "\n" + GATE_LINE,
            1,
        )
        changes.append("inserted_render_gate_call")

    if "_apply_answer_strategy_render_gate" not in original:
        content = content.rstrip() + "\n\n\n" + HELPER_BLOCK.strip() + "\n"
        changes.append("inserted_render_gate_helpers")

    if content == original:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "changed": False,
                "message": "already patched",
            }
        )
        return 0

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "changed": True,
            "changes": changes,
        }
    )

    print("workflow.py answer strategy render gate patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())