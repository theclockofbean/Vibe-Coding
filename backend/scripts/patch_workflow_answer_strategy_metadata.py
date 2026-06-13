"""Patch workflow.py to apply answer strategy metadata after unified KB routing."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

ROUTER_LINE: Final[str] = "        new_state = _apply_unified_kb_routing(new_state)"
ANSWER_STRATEGY_LINE: Final[str] = (
    "        new_state = _apply_answer_strategy_metadata(new_state)"
)

HELPER_BLOCK: Final[str] = '''
def _apply_answer_strategy_metadata(
    state: AgentState,
) -> AgentState:
    """Apply multi-module answer strategy metadata."""

    from app.agent.answering.multimodule_answer_strategy import (
        decide_answer_strategy,
    )

    new_state = cast(AgentState, dict(state))
    metadata = _ensure_metadata(new_state)
    state_extras = cast(dict[str, Any], new_state)

    query = _state_current_query_for_unified_kb_routing(new_state)
    selected_module = _state_selected_module_for_answer_strategy(new_state)
    candidate_modules = _state_candidate_modules_for_answer_strategy(new_state)
    conflict_type = _state_conflict_type_for_answer_strategy(new_state)

    decision = decide_answer_strategy(
        query=query,
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        conflict_type=conflict_type,
    )

    metadata.update(decision.to_metadata())

    state_extras["answer_strategy_mode"] = decision.strategy_mode
    state_extras["answer_primary_module"] = decision.primary_module
    state_extras["answer_candidate_modules"] = decision.candidate_modules
    state_extras["answer_boundary_notes"] = decision.boundary_notes
    state_extras["answer_split_required"] = decision.split_required
    state_extras["answer_handoff_required"] = decision.handoff_required
    state_extras["answer_safety_blocked"] = decision.safety_blocked
    state_extras["answer_forbidden_commitment_detected"] = (
        decision.forbidden_commitment_detected
    )

    return new_state


def _state_selected_module_for_answer_strategy(
    state: AgentState,
) -> str | None:
    """Return selected module for answer strategy."""

    metadata = _ensure_metadata(state)
    state_extras = cast(dict[str, Any], state)

    value = (
        state_extras.get("selected_module")
        or metadata.get("unified_kb_selected_module")
        or metadata.get("retrieval_selected_module")
    )

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def _state_candidate_modules_for_answer_strategy(
    state: AgentState,
) -> list[str]:
    """Return candidate modules for answer strategy."""

    metadata = _ensure_metadata(state)
    state_extras = cast(dict[str, Any], state)

    value = (
        state_extras.get("candidate_modules")
        or metadata.get("unified_kb_candidate_modules")
        or metadata.get("routing_candidate_modules")
    )

    if not isinstance(value, list):
        selected_module = _state_selected_module_for_answer_strategy(state)
        return [selected_module] if selected_module else []

    return [
        str(item).strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def _state_conflict_type_for_answer_strategy(
    state: AgentState,
) -> str | None:
    """Return conflict type for answer strategy."""

    metadata = _ensure_metadata(state)
    state_extras = cast(dict[str, Any], state)

    value = (
        state_extras.get("routing_conflict_type")
        or metadata.get("unified_kb_conflict_type")
        or metadata.get("routing_conflict_type")
    )

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None
'''


def main() -> int:
    """Patch workflow.py."""

    print("=" * 80)
    print("patching workflow.py for answer strategy metadata")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    if ANSWER_STRATEGY_LINE not in content:
        if ROUTER_LINE not in content:
            pprint({"error": "unified KB router line not found"})
            return 1

        content = content.replace(
            ROUTER_LINE,
            ROUTER_LINE + "\n" + ANSWER_STRATEGY_LINE,
            1,
        )
        changes.append("inserted_answer_strategy_call")

    if "_apply_answer_strategy_metadata" not in original:
        content = content.rstrip() + "\n\n\n" + HELPER_BLOCK.strip() + "\n"
        changes.append("inserted_answer_strategy_helpers")

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

    print("workflow.py answer strategy metadata patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())