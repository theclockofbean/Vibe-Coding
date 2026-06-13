"""Patch workflow to reapply LLM intent module after handler.

Handler / UnifiedTextQAService may overwrite selected_module based on legacy
rule-based routing. If IntentNode has already applied a validated LLM intent,
the workflow should preserve that module before retrieval/rendering.
"""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")


def patch_handler_node(source: str) -> str:
    """Insert LLM intent override before final return of handler_node."""

    marker = "_reapply_llm_intent_module_after_handler(next_state)"

    if marker in source:
        return source

    start = source.index("    def handler_node(")

    try:
        end = source.index("\n    def retrieval_node(", start)
    except ValueError as exc:
        raise RuntimeError("retrieval_node anchor not found") from exc

    method = source[start:end]
    lines = method.splitlines(keepends=True)

    return_index: int | None = None

    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].lstrip()

        if lines[index].startswith("        return ") and stripped.startswith("return "):
            return_index = index
            break

    if return_index is None:
        raise RuntimeError("no final return statement found in handler_node")

    insertion = [
        "\n",
        "        _reapply_llm_intent_module_after_handler(next_state)\n",
        "\n",
    ]

    lines[return_index:return_index] = insertion
    patched_method = "".join(lines)

    return source[:start] + patched_method + source[end:]


def patch_helper(source: str) -> str:
    """Add helper once."""

    if "def _reapply_llm_intent_module_after_handler(" in source:
        return source

    helper_anchor = "\ndef _apply_llm_intent_fallback_if_needed("

    helper = '''

def _reapply_llm_intent_module_after_handler(
    state: AgentState,
) -> None:
    """Reapply validated LLM intent module after handler payload merge.

    The handler may call legacy unified routing and overwrite selected_module.
    For low-confidence or forced LLM-intent cases, a validated and applied LLM
    intent should be preserved before retrieval.
    """

    metadata = _ensure_metadata(state)
    applied_intent = _optional_state_str(
        metadata.get("llm_intent_applied_intent")
    )

    if metadata.get("llm_intent_applied") is not True:
        return

    if applied_intent not in {"spec", "price", "logistics", "quality", "general"}:
        return

    previous_selected_module = _optional_state_str(state.get("selected_module"))

    if applied_intent in {"spec", "price", "logistics", "quality"}:
        state["intent"] = applied_intent
        state["selected_module"] = applied_intent
        state["candidate_modules"] = [applied_intent]
        state["route_status"] = "matched"
        state["workflow_route"] = applied_intent
    elif applied_intent == "general":
        state["intent"] = "general"
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]

    metadata["llm_intent_reapplied_after_handler"] = True
    metadata["llm_intent_reapplied_module"] = applied_intent
    metadata["llm_intent_previous_selected_module_after_handler"] = (
        previous_selected_module
    )

'''

    if helper_anchor not in source:
        raise RuntimeError("LLM intent helper anchor not found")

    return source.replace(helper_anchor, helper + helper_anchor, 1)


content = patch_handler_node(content)
content = patch_helper(content)

target.write_text(content, encoding="utf-8")

print("patched workflow to reapply LLM intent after handler")