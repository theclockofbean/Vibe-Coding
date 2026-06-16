"""Patch Workflow to reapply Phase 3-I-I priority intent after legacy routing."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


HELPER_FUNCTION: Final[str] = '''
def _reapply_phase3ii_priority_intent_module(
    state: AgentState,
) -> AgentState:
    """Reapply Phase 3-I-I priority intent after legacy route overrides.

    The local priority classifier can correctly identify price, logistics,
    quality, spec, or escalation. Legacy parser/handler/force-route steps may
    still overwrite selected_module later, so this function restores the
    priority intent immediately before retrieval/render metadata is finalized.
    """

    metadata = _state_metadata(state)

    priority_metadata = metadata.get("llm_intent_metadata")
    priority_metadata_dict: dict[str, object] = {}

    if isinstance(priority_metadata, dict):
        priority_metadata_dict = {
            str(key): value for key, value in priority_metadata.items()
        }

    result_metadata = metadata.get("llm_intent_result")
    result_metadata_dict: dict[str, object] = {}

    if isinstance(result_metadata, dict):
        nested_metadata = result_metadata.get("metadata")
        if isinstance(nested_metadata, dict):
            result_metadata_dict = {
                str(key): value for key, value in nested_metadata.items()
            }

    priority_router_used = (
        priority_metadata_dict.get("phase3ii_priority_router") is True
        or result_metadata_dict.get("phase3ii_priority_router") is True
        or priority_metadata_dict.get("resolver")
        == "phase3ii_priority_local_cue_resolution"
        or result_metadata_dict.get("resolver")
        == "phase3ii_priority_local_cue_resolution"
    )

    if priority_router_used is not True:
        return state

    priority_intent = _optional_state_str(
        metadata.get("llm_intent_applied_intent")
    ) or _optional_state_str(metadata.get("llm_intent"))

    if priority_intent not in {
        "spec",
        "price",
        "logistics",
        "quality",
        "escalation",
    }:
        return state

    previous_selected_module = _optional_state_str(state.get("selected_module"))
    previous_intent = _optional_state_str(state.get("intent"))

    state["intent"] = priority_intent
    state["selected_module"] = priority_intent
    state["candidate_modules"] = [priority_intent]

    if priority_intent in {"spec", "price", "logistics", "quality"}:
        state["workflow_route"] = priority_intent  # type: ignore[typeddict-unknown-key]
    else:
        state["workflow_route"] = "general"  # type: ignore[typeddict-unknown-key]

    metadata["phase3ii_priority_intent_reapplied"] = True
    metadata["phase3ii_priority_intent"] = priority_intent
    metadata["phase3ii_priority_previous_selected_module"] = previous_selected_module
    metadata["phase3ii_priority_previous_intent"] = previous_intent

    return state
'''


def main() -> int:
    """Patch workflow priority intent reapply."""

    print("=" * 80)
    print("patching Phase 3-I-I workflow priority intent reapply")

    errors: list[str] = []
    changes: list[str] = []

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    if "_reapply_phase3ii_priority_intent_module" not in content:
        anchor = "\ndef _reapply_llm_intent_module_after_handler("
        if anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(anchor, HELPER_FUNCTION + "\n" + anchor, 1)
            changes.append("inserted phase3ii priority reapply helper")
    else:
        changes.append("phase3ii priority reapply helper already present")

    old_allowed = (
        '    if applied_intent not in {"spec", "price", "logistics", "quality", "general"}:\n'
    )
    new_allowed = (
        '    if applied_intent not in {\n'
        '        "spec",\n'
        '        "price",\n'
        '        "logistics",\n'
        '        "quality",\n'
        '        "general",\n'
        '        "escalation",\n'
        '    }:\n'
    )

    if old_allowed in content:
        content = content.replace(old_allowed, new_allowed, 1)
        changes.append("allowed escalation in llm intent reapply guard")
    else:
        changes.append("llm intent reapply guard already changed or anchor not present")

    old_escalation_branch = (
        '    elif result.intent == "escalation":\n'
        '        state["selected_module"] = "general"\n'
        '        state["candidate_modules"] = ["general"]\n'
    )
    new_escalation_branch = (
        '    elif result.intent == "escalation":\n'
        '        state["selected_module"] = "escalation"\n'
        '        state["candidate_modules"] = ["escalation"]\n'
    )

    if old_escalation_branch in content:
        content = content.replace(old_escalation_branch, new_escalation_branch, 1)
        changes.append("preserved escalation selected_module in llm intent apply")
    else:
        changes.append("escalation apply branch already changed or anchor not present")

    old_handler_branch = (
        '    if applied_intent in {"spec", "price", "logistics", "quality"}:\n'
        '        state["intent"] = applied_intent\n'
        '        state["selected_module"] = applied_intent\n'
        '        state["candidate_modules"] = [applied_intent]\n'
        '        state["workflow_route"] = applied_intent  # type: ignore[typeddict-unknown-key]\n'
        '    elif applied_intent == "general":\n'
    )
    new_handler_branch = (
        '    if applied_intent in {"spec", "price", "logistics", "quality"}:\n'
        '        state["intent"] = applied_intent\n'
        '        state["selected_module"] = applied_intent\n'
        '        state["candidate_modules"] = [applied_intent]\n'
        '        state["workflow_route"] = applied_intent  # type: ignore[typeddict-unknown-key]\n'
        '    elif applied_intent == "escalation":\n'
        '        state["intent"] = "escalation"\n'
        '        state["selected_module"] = "escalation"\n'
        '        state["candidate_modules"] = ["escalation"]\n'
        '        state["workflow_route"] = "general"  # type: ignore[typeddict-unknown-key]\n'
        '    elif applied_intent == "general":\n'
    )

    if old_handler_branch in content:
        content = content.replace(old_handler_branch, new_handler_branch, 1)
        changes.append("added escalation branch to llm intent reapply helper")
    else:
        changes.append("handler reapply branch already changed or anchor not present")

    call_anchor = (
        "        new_state = _force_spec_route_for_spec_kb_question(new_state)\n"
        "        spec_state, real_spec_kb_used = _try_real_spec_kb_retrieval(dict(new_state))\n"
        "        if real_spec_kb_used:\n"
        "            return spec_state\n"
        "        new_state = spec_state\n"
    )
    replacement = (
        "        new_state = _force_spec_route_for_spec_kb_question(new_state)\n"
        "        spec_state, real_spec_kb_used = _try_real_spec_kb_retrieval(dict(new_state))\n"
        "        if real_spec_kb_used:\n"
        "            return spec_state\n"
        "        new_state = spec_state\n"
        "        new_state = _reapply_phase3ii_priority_intent_module(new_state)\n"
    )

    if "_reapply_phase3ii_priority_intent_module(new_state)" not in content:
        if call_anchor not in content:
            errors.append("priority reapply call insertion anchor not found")
        else:
            content = content.replace(call_anchor, replacement, 1)
            changes.append("inserted priority reapply call after legacy route overrides")
    else:
        changes.append("priority reapply call already present")

    if content != original and not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I workflow priority intent reapply patch failed")
        return 1

    print("Phase 3-I-I workflow priority intent reapply patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())