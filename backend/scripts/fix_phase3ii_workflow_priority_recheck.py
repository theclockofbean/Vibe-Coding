"""Fix Phase 3-I-I workflow priority intent reapply by local recheck."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


QUERY_HELPER: Final[str] = '''
def _phase3ii_priority_intent_query_text(
    state: AgentState,
) -> str:
    """Return user query text for Phase 3-I-I priority intent recheck."""

    state_dict = dict(state)

    for key in (
        "user_text",
        "query",
        "input_text",
        "latest_user_text",
        "raw_user_text",
    ):
        value = state_dict.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata = _ensure_metadata(state)

    for key in (
        "user_text",
        "query",
        "input_text",
        "latest_user_text",
        "raw_user_text",
    ):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    messages_value = state_dict.get("messages")
    if isinstance(messages_value, list):
        for item in reversed(messages_value):
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if role in {"user", "customer"} and isinstance(content, str):
                if content.strip():
                    return content.strip()

    return ""
'''


OLD_BLOCK: Final[str] = '''    if priority_router_used is not True:
        return state

    priority_intent = _optional_state_str(
        metadata.get("llm_intent_applied_intent")
    ) or _optional_state_str(metadata.get("llm_intent"))
'''


NEW_BLOCK: Final[str] = '''    query_text = _phase3ii_priority_intent_query_text(state)

    if query_text:
        from app.agent.llm.intent_classifier import classify_intent_by_keywords

        local_priority_result = classify_intent_by_keywords(query_text)

        if local_priority_result.metadata.get("phase3ii_priority_router") is True:
            priority_router_used = True
            metadata["phase3ii_priority_local_recheck"] = (
                local_priority_result.to_dict()
            )
            metadata["phase3ii_priority_local_recheck_intent"] = (
                local_priority_result.intent
            )

    if priority_router_used is not True:
        return state

    priority_intent = _optional_state_str(
        metadata.get("phase3ii_priority_local_recheck_intent")
    ) or _optional_state_str(
        metadata.get("llm_intent_applied_intent")
    ) or _optional_state_str(metadata.get("llm_intent"))
'''


def main() -> int:
    """Patch workflow priority local recheck."""

    print("=" * 80)
    print("fixing Phase 3-I-I workflow priority local recheck")

    errors: list[str] = []
    changes: list[str] = []

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    if "_phase3ii_priority_intent_query_text" not in content:
        anchor = "\ndef _reapply_phase3ii_priority_intent_module("
        if anchor not in content:
            errors.append("query helper insertion anchor not found")
        else:
            content = content.replace(anchor, QUERY_HELPER + "\n" + anchor, 1)
            changes.append("inserted phase3ii priority query text helper")
    else:
        changes.append("phase3ii priority query text helper already present")

    if "phase3ii_priority_local_recheck" not in content:
        if OLD_BLOCK not in content:
            errors.append("priority local recheck insertion anchor not found")
        else:
            content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
            changes.append("inserted local priority classifier recheck")
    else:
        changes.append("local priority classifier recheck already present")

    if content != original and not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I workflow priority local recheck fix failed")
        return 1

    print("Phase 3-I-I workflow priority local recheck fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())