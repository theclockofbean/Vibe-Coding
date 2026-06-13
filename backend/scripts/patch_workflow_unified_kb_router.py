"""Patch workflow.py to apply unified KB router before real KB retrieval."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

QUALITY_HOOK_FRAGMENT: Final[str] = (
    "quality_state, real_quality_kb_used = "
    "_try_real_quality_kb_retrieval"
)

UNIFIED_ROUTER_LINE: Final[str] = (
    "        new_state = _apply_unified_kb_routing(new_state)"
)

OVERRIDE_GUARD_LINES: Final[list[str]] = [
    '    if metadata.get("unified_kb_router_used") is True:',
    "        return new_state",
]

UNIFIED_ROUTER_HELPER: Final[str] = '''
def _apply_unified_kb_routing(
    state: AgentState,
) -> AgentState:
    """Apply unified KB routing decision before real KB retrieval."""

    from app.agent.routing.unified_kb_router import route_query_to_kb

    new_state = cast(AgentState, dict(state))
    metadata = _ensure_metadata(new_state)

    query = _state_current_query_for_unified_kb_routing(new_state)
    decision = route_query_to_kb(query)

    metadata["unified_kb_router_enabled"] = True
    metadata["unified_kb_router_used"] = decision.selected_module is not None
    metadata["unified_kb_selected_module"] = decision.selected_module
    metadata["unified_kb_candidate_modules"] = decision.candidate_modules
    metadata["unified_kb_conflict_type"] = decision.conflict_type
    metadata["unified_kb_matched_signals"] = decision.matched_signals
    metadata["unified_kb_reason"] = decision.reason
    metadata["unified_kb_risk_tags"] = decision.risk_tags

    if decision.selected_module is None:
        return new_state

    state_extras = cast(dict[str, Any], new_state)
    state_extras["selected_module"] = decision.selected_module
    state_extras["intent"] = decision.selected_module
    state_extras["candidate_modules"] = decision.candidate_modules
    state_extras["routing_conflict_type"] = decision.conflict_type
    state_extras["routing_reason"] = decision.reason
    state_extras["routing_risk_tags"] = decision.risk_tags

    return new_state


def _state_current_query_for_unified_kb_routing(
    state: AgentState,
) -> str:
    """Return current query text for unified KB routing."""

    for key in ("user_text", "current_message", "user_message", "query"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""
'''


def main() -> int:
    """Patch workflow.py."""

    print("=" * 80)
    print("patching workflow.py for unified KB router")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content
    lines = content.splitlines()
    changes: list[str] = []

    if "_apply_unified_kb_routing" not in content:
        lines = insert_unified_router_before_quality_hook(lines=lines)
        changes.append("inserted_unified_router_hook")

    content = "\n".join(lines) + "\n"

    if "_state_current_query_for_unified_kb_routing" not in content:
        content = content.rstrip() + "\n\n\n" + UNIFIED_ROUTER_HELPER.strip() + "\n"
        changes.append("inserted_unified_router_helpers")

    content, logistics_changed = insert_override_guard(
        content=content,
        function_name="_force_logistics_route_for_delivery_question",
    )

    if logistics_changed:
        changes.append("guarded_logistics_override")

    content, spec_changed = insert_override_guard(
        content=content,
        function_name="_force_spec_route_for_spec_kb_question",
    )

    if spec_changed:
        changes.append("guarded_spec_override")

    if content == original:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "changed": False,
                "message": "already patched or no matching changes needed",
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

    print("workflow.py unified KB router patch completed")
    return 0


def insert_unified_router_before_quality_hook(
    *,
    lines: list[str],
) -> list[str]:
    """Insert unified router call before first real Quality KB hook."""

    for index, line in enumerate(lines):
        if QUALITY_HOOK_FRAGMENT in line:
            return lines[:index] + [UNIFIED_ROUTER_LINE] + lines[index:]

    raise ValueError("Quality KB hook anchor not found")


def insert_override_guard(
    *,
    content: str,
    function_name: str,
) -> tuple[str, bool]:
    """Insert guard into legacy route override helper."""

    function_start = content.find(f"def {function_name}(")

    if function_start < 0:
        return content, False

    next_function_start = content.find("\ndef ", function_start + 1)

    if next_function_start < 0:
        function_block = content[function_start:]
        suffix = ""
    else:
        function_block = content[function_start:next_function_start]
        suffix = content[next_function_start:]

    if 'metadata.get("unified_kb_router_used") is True' in function_block:
        return content, False

    metadata_line = "    metadata = _ensure_metadata(new_state)\n"

    if metadata_line not in function_block:
        raise ValueError(f"{function_name}: metadata anchor not found")

    guarded_block = function_block.replace(
        metadata_line,
        metadata_line + "\n".join(OVERRIDE_GUARD_LINES) + "\n\n",
        1,
    )

    return content[:function_start] + guarded_block + suffix, True


if __name__ == "__main__":
    raise SystemExit(main())