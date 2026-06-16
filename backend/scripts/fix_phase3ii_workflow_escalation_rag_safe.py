"""Make Phase 3-I-I escalation priority intent RAG-safe."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


OLD_BLOCK: Final[str] = '''    state["intent"] = priority_intent
    state["selected_module"] = priority_intent
    state["candidate_modules"] = [priority_intent]

    if priority_intent in {"spec", "price", "logistics", "quality"}:
        state["workflow_route"] = priority_intent  # type: ignore[typeddict-unknown-key]
    else:
        state["workflow_route"] = "general"  # type: ignore[typeddict-unknown-key]
'''


NEW_BLOCK: Final[str] = '''    state["intent"] = priority_intent

    if priority_intent == "escalation":
        # Escalation is a business intent, not a RAG knowledge module.
        # Keep it in metadata/intent, but use a RAG-safe selected_module.
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]
        state["workflow_route"] = "general"  # type: ignore[typeddict-unknown-key]
    else:
        state["selected_module"] = priority_intent
        state["candidate_modules"] = [priority_intent]
        state["workflow_route"] = priority_intent  # type: ignore[typeddict-unknown-key]
'''


def main() -> int:
    """Patch escalation selected_module before RAG retrieval."""

    print("=" * 80)
    print("fixing Phase 3-I-I escalation selected_module for RAG safety")

    errors: list[str] = []
    changes: list[str] = []

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    if OLD_BLOCK in content:
        content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
        changes.append("made escalation priority intent RAG-safe")
    elif "Escalation is a business intent, not a RAG knowledge module." in content:
        changes.append("escalation RAG-safe patch already present")
    else:
        errors.append("escalation RAG-safe block anchor not found")

    if content != original and not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I escalation RAG-safe fix failed")
        return 1

    print("Phase 3-I-I escalation RAG-safe fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())