"""Patch workflow RenderNode to use GroundedRenderer."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")

start = content.index("    def render_node(")

try:
    end = content.index("\ndef build_agent_workflow", start)
except ValueError as exc:
    raise RuntimeError("build_agent_workflow anchor not found") from exc

replacement = '''    def render_node(
        self,
        state: AgentState,
    ) -> AgentState:
        """Render grounded final response.

        Grounded RenderNode uses structured handler output, safe RAG evidence,
        business rules, and optional safe LLM expression support. It does not
        write database records.
        """

        new_state = _copy_state(state)
        metadata = _ensure_metadata(new_state)

        _mark_visited(new_state, "render")

        try:
            render_input, render_output = _run_grounded_render_for_state(new_state)

            new_state["render_input"] = render_input
            new_state["render_output"] = render_output
            new_state["final_response"] = render_output.get("final_response")
            new_state["response_sources"] = _as_dict_list(
                render_output.get("response_sources")
            )
            new_state["response_warnings"] = _as_text_list(
                render_output.get("response_warnings")
            )
            new_state["render_risk_flags"] = _as_text_list(
                render_output.get("risk_flags")
            )
            new_state["render_used_llm_output"] = bool(
                render_output.get("used_llm_output")
            )
            new_state["is_grounded_response"] = bool(
                render_output.get("is_grounded")
            )

            if render_output.get("needs_handoff") is True:
                new_state["handoff_required"] = True
                new_state["human_handoff"] = True

            new_state["warnings"] = _deduplicate_text_list(
                [
                    *_as_text_list(new_state.get("warnings")),
                    *_as_text_list(render_output.get("response_warnings")),
                ]
            )
            new_state["risk_reasons"] = _deduplicate_text_list(
                [
                    *_as_text_list(new_state.get("risk_reasons")),
                    *_as_text_list(render_output.get("risk_reasons")),
                ]
            )

            metadata["response_ready"] = True
            metadata["render_mode"] = render_output.get("metadata", {}).get(
                "render_mode"
            )
            metadata["render_is_grounded"] = render_output.get("is_grounded")
            metadata["render_used_llm_output"] = render_output.get(
                "used_llm_output"
            )
            metadata["render_source_count"] = len(
                _as_dict_list(render_output.get("response_sources"))
            )
            metadata["render_warning_count"] = len(
                _as_text_list(render_output.get("response_warnings"))
            )
            metadata["render_safety_blocked"] = render_output.get(
                "metadata", {}
            ).get("render_safety_blocked")
            metadata["render_fallback_reason"] = render_output.get(
                "metadata", {}
            ).get("render_fallback_reason")

        except (RuntimeError, ValueError, TypeError) as exc:
            fallback_response = _optional_state_str(new_state.get("answer_text"))

            if fallback_response is None:
                fallback_response = (
                    "当前信息不足，无法形成可靠答复。请补充 SKU、数量、"
                    "收货地区或具体问题后转人工确认。"
                )
                new_state["handoff_required"] = True
                new_state["human_handoff"] = True

            new_state["final_response"] = fallback_response
            new_state["render_input"] = {}
            new_state["render_output"] = {}
            new_state["response_sources"] = []
            new_state["response_warnings"] = ["grounded render node fallback"]
            new_state["render_risk_flags"] = []
            new_state["render_used_llm_output"] = False
            new_state["is_grounded_response"] = False

            metadata["response_ready"] = True
            metadata["render_mode"] = "workflow_render_fallback"
            metadata["render_is_grounded"] = False
            metadata["render_used_llm_output"] = False
            metadata["render_source_count"] = 0
            metadata["render_warning_count"] = 1
            metadata["render_safety_blocked"] = False
            metadata["render_fallback_reason"] = f"{type(exc).__name__}: {exc}"

        metadata["workflow_finished_at"] = _utc_now_iso()

        return new_state

'''

content = content[:start] + replacement + content[end:]

if "def _run_grounded_render_for_state(" not in content:
    helper_anchor = "\ndef _run_offline_llm_for_state("
    helper = '''

def _run_grounded_render_for_state(
    state: AgentState,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run RenderContextBuilder and GroundedRenderer for workflow state."""

    import os

    from app.agent.rendering.context import RenderContextBuilder
    from app.agent.rendering.grounded_renderer import GroundedRenderer

    if os.getenv("AGENT_RENDER_FORCE_ERROR", "").strip() == "1":
        raise RuntimeError("forced grounded render node error for regression check")

    render_input = RenderContextBuilder().from_state(state)
    render_output = GroundedRenderer().render(render_input)

    return render_input.to_dict(), render_output.to_dict()

'''
    if helper_anchor not in content:
        raise RuntimeError("LLM helper anchor not found")
    content = content.replace(helper_anchor, helper + helper_anchor)

target.write_text(content, encoding="utf-8")

print("patched workflow RenderNode with GroundedRenderer")