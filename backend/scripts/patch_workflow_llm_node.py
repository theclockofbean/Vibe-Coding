"""Patch LangGraph workflow with LLMNode."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")

if "    def llm_node(" not in content:
    anchor = "\n    def risk_control_node("
    llm_node = '''    def llm_node(
        self,
        state: AgentState,
    ) -> AgentState:
        """Run offline LLM client and safety guard.

        LLM output is recorded for later grounded rendering work. It does not
        modify final_response, answer_text, handoff flags, or database state.
        """

        new_state = _copy_state(state)
        metadata = _ensure_metadata(new_state)

        _mark_visited(new_state, "llm")

        llm_enabled = _is_llm_node_enabled()

        if not llm_enabled:
            new_state["llm_used"] = False
            new_state["llm_error"] = None
            new_state["llm_output"] = None
            new_state["llm_safety_flags"] = []

            metadata["llm_enabled"] = False
            metadata["llm_used"] = False
            metadata["llm_fallback_reason"] = "llm_node_disabled"

            return new_state

        try:
            request, response = _run_offline_llm_for_state(new_state)

            new_state["llm_request"] = request
            new_state["llm_response"] = response
            new_state["llm_output"] = response.get("content")
            new_state["llm_safety_flags"] = _as_text_list(
                response.get("safety_flags")
            )
            new_state["llm_used"] = response.get("error") is None
            new_state["llm_error"] = _optional_state_str(response.get("error"))

            metadata["llm_enabled"] = True
            metadata["llm_used"] = new_state["llm_used"]
            metadata["llm_provider"] = response.get("provider")
            metadata["llm_model"] = response.get("model")
            metadata["llm_task_type"] = request.get("task_type")
            metadata["llm_latency_ms"] = response.get("latency_ms")
            metadata["llm_is_safe"] = response.get("is_safe")
            metadata["llm_needs_handoff"] = response.get("needs_handoff")
            metadata["llm_fallback_reason"] = None

        except (RuntimeError, ValueError) as exc:
            new_state["llm_request"] = {}
            new_state["llm_response"] = {}
            new_state["llm_output"] = None
            new_state["llm_safety_flags"] = ["llm_node_error"]
            new_state["llm_used"] = False
            new_state["llm_error"] = f"{type(exc).__name__}: {exc}"

            metadata["llm_enabled"] = True
            metadata["llm_used"] = False
            metadata["llm_error"] = new_state["llm_error"]
            metadata["llm_fallback_reason"] = "llm_node_error"

        return new_state

'''
    content = content.replace(anchor, "\n" + llm_node + anchor)

if "def _run_offline_llm_for_state(" not in content:
    helper_anchor = "\ndef _retrieve_qdrant_rag_chunks("
    helper = '''

def _run_offline_llm_for_state(
    state: AgentState,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run offline RuleBasedLLMClient for state and guard its response."""

    import os

    from app.agent.llm.client import RuleBasedLLMClient
    from app.agent.llm.safety import LLMSafetyGuard
    from app.agent.llm.schemas import LLMRequest

    if os.getenv("AGENT_LLM_FORCE_ERROR", "").strip() == "1":
        raise RuntimeError("forced llm node error for regression check")

    task_type = _infer_llm_task_type(state)

    request = LLMRequest(
        task_type=task_type,
        user_text=str(state.get("user_text") or ""),
        context_blocks=_build_llm_context_blocks(state),
        retrieved_chunks=_as_dict_list(state.get("retrieved_chunks")),
        structured_facts=_extract_llm_structured_facts(state),
        business_rules=_build_llm_business_rules(),
        metadata={
            "selected_module": state.get("selected_module"),
            "handler_status": state.get("handler_status"),
            "handoff_required": state.get("handoff_required"),
        },
    )

    raw_response = RuleBasedLLMClient().generate(request)
    guarded_response = LLMSafetyGuard().guard_response(raw_response)

    return request.to_dict(), guarded_response.to_dict()


def _is_llm_node_enabled() -> bool:
    """Return whether LLM node is enabled."""

    import os

    value = os.getenv("AGENT_LLM_NODE_ENABLED", "1").strip().lower()

    return value not in {"0", "false", "no", "off"}


def _infer_llm_task_type(
    state: AgentState,
) -> str:
    """Infer safe offline LLM task type."""

    if state.get("handoff_required") is True:
        return "draft_handoff_note"

    retrieved_chunks = _as_dict_list(state.get("retrieved_chunks"))

    if retrieved_chunks:
        return "summarize_evidence"

    return "rule_based_test"


def _build_llm_context_blocks(
    state: AgentState,
) -> list[str]:
    """Build safe context blocks for LLM."""

    blocks: list[str] = []

    answer_text = _optional_state_str(state.get("answer_text"))

    if answer_text is not None:
        blocks.append(f"结构化模块答复：{answer_text}")

    selected_module = _optional_state_str(state.get("selected_module"))

    if selected_module is not None:
        blocks.append(f"已选模块：{selected_module}")

    return blocks


def _extract_llm_structured_facts(
    state: AgentState,
) -> dict[str, Any]:
    """Extract structured facts for LLM."""

    module_payload = state.get("module_payload")

    if isinstance(module_payload, dict):
        return {
            str(key): value
            for key, value in module_payload.items()
        }

    return {}


def _build_llm_business_rules() -> list[str]:
    """Return LLM business rules."""

    return [
        "LLM 输出不是事实来源。",
        "LLM 不得生成价格、库存、物流、质量、售后承诺。",
        "最终结论必须以结构化数据、业务规则或人工确认为准。",
        "证据不足时应拒答或转人工。",
    ]


def _as_dict_list(
    value: object,
) -> list[dict[str, Any]]:
    """Return list of dictionaries."""

    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []

    for item in value:
        if isinstance(item, dict):
            result.append(
                {
                    str(key): item_value
                    for key, item_value in item.items()
                }
            )

    return result

'''
    content = content.replace(helper_anchor, helper + helper_anchor)

if 'workflow.add_node("llm", nodes.llm_node)' not in content:
    content = content.replace(
        'workflow.add_node("risk_control", nodes.risk_control_node)',
        'workflow.add_node("llm", nodes.llm_node)\n    workflow.add_node("risk_control", nodes.risk_control_node)',
    )

content = content.replace(
    'workflow.add_edge("retrieval", "risk_control")',
    'workflow.add_edge("retrieval", "llm")\n    workflow.add_edge("llm", "risk_control")',
)

target.write_text(content, encoding="utf-8")

print("patched workflow with LLMNode")