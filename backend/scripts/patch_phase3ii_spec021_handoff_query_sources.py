"""Make unsupported thread handoff detection read more workflow query fields."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

OLD_TEXT: Final[str] = '''def _answer_strategy_query_text(state: Any | None) -> str | None:
    """Read original user query text from workflow state."""

    if not isinstance(state, dict):
        return None

    for key in ("user_message", "query", "raw_text", "text"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return None
'''

NEW_TEXT: Final[str] = '''def _answer_strategy_query_text(state: Any | None) -> str | None:
    """Read original user query text from workflow state or metadata-like values."""

    if not isinstance(state, dict):
        return None

    query_keys = (
        "user_message",
        "current_user_message",
        "last_user_message",
        "input_text",
        "user_input",
        "query",
        "question",
        "raw_text",
        "text",
        "message",
    )

    for key in query_keys:
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = state.get("messages")

    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict):
                value = item.get("content") or item.get("text")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            elif isinstance(item, str) and item.strip():
                return item.strip()

    return None
'''


def main() -> int:
    """Patch query text extraction."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content
    errors: list[str] = []
    changes: list[str] = []

    if NEW_TEXT in content:
        changes.append("query text extraction already patched")
    elif OLD_TEXT in content:
        content = content.replace(OLD_TEXT, NEW_TEXT, 1)
        changes.append("patched query text extraction")
    else:
        errors.append("query text extraction anchor not found")

    if content != original and not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())