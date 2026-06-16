"""Fix I3 workflow LLM checker initial state signature mismatch."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ii_workflow_real_llm_offline.py"
)


def main() -> int:
    """Patch I3 checker to build initial state by signature."""

    print("=" * 80)
    print("fixing I3 workflow LLM checker initial state signature")

    if not CHECK_FILE.exists():
        pprint({"error": f"missing check file: {CHECK_FILE}"})
        return 1

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    if "import inspect" not in content:
        content = content.replace(
            "import os\n",
            "import inspect\nimport os\n",
            1,
        )
        changes.append("added inspect import")

    old_block = '''    state = create_initial_agent_state(
        user_text=query,
        session_id=f"{case_id.lower()}-session",
        conversation_id=f"{case_id.lower()}-conversation",
    )
'''

    new_block = '''    state = build_initial_state(
        user_text=query,
        session_id=f"{case_id.lower()}-session",
        conversation_id=f"{case_id.lower()}-conversation",
    )
'''

    if old_block in content:
        content = content.replace(old_block, new_block, 1)
        changes.append("replaced direct create_initial_agent_state call")
    elif "state = build_initial_state(" in content:
        changes.append("initial state call already patched")
    else:
        pprint({"error": "initial state call anchor not found"})
        return 1

    helper_block = '''
def build_initial_state(
    *,
    user_text: str,
    session_id: str,
    conversation_id: str,
) -> Any:
    """Build initial AgentState using only supported signature parameters."""

    signature = inspect.signature(create_initial_agent_state)
    supported = set(signature.parameters)

    candidate_kwargs: dict[str, Any] = {
        "user_text": user_text,
        "session_id": session_id,
        "conversation_id": conversation_id,
        "channel": "api",
        "user_id": "phase3ii-workflow-real-llm-offline",
    }

    kwargs = {
        key: value
        for key, value in candidate_kwargs.items()
        if key in supported
    }

    factory = cast(Any, create_initial_agent_state)

    return factory(**kwargs)
'''

    if "def build_initial_state(" not in content:
        insert_anchor = "\ndef mask_env_value(\n"
        if insert_anchor not in content:
            pprint({"error": "helper insertion anchor not found"})
            return 1

        content = content.replace(
            insert_anchor,
            "\n" + helper_block.strip() + "\n\n\n" + "def mask_env_value(\n",
            1,
        )
        changes.append("inserted build_initial_state helper")
    else:
        changes.append("build_initial_state helper already exists")

    if content != original:
        CHECK_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "check_file": str(CHECK_FILE),
            "changed": content != original,
            "changes": changes,
        }
    )

    print("I3 workflow LLM checker initial state signature fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())