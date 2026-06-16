"""Repair spec unsupported thread handoff helpers."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

WORKFLOW_FILE = Path("app/agent/workflow.py")


UNSUPPORTED_THREAD_FUNC = '''def _answer_strategy_unsupported_thread_spec(
    *,
    metadata: dict[str, Any],
    state: Any | None,
) -> str | None:
    """Return unsupported thread spec mentioned in a spec handoff query."""

    candidate_modules = _as_text_list(metadata.get("answer_candidate_modules"))
    primary_module = str(metadata.get("answer_primary_module") or "")

    if primary_module != "spec" and "spec" not in candidate_modules:
        return None

    query_text = _answer_strategy_query_text(state)

    if query_text is None:
        return None

    normalized_query = query_text.upper()

    for thread_spec in ("M14", "M16", "M18", "M20"):
        if thread_spec in normalized_query:
            return thread_spec

    return None


'''


QUERY_TEXT_FUNCS = '''def _answer_strategy_query_text(state: Any | None) -> str | None:
    """Read original user query text from workflow state."""

    if state is None:
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
        value = _answer_strategy_state_value(state, key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = _answer_strategy_state_value(state, "messages")

    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict):
                value = item.get("content") or item.get("text")
            elif isinstance(item, str):
                value = item
            else:
                value = getattr(item, "content", None) or getattr(item, "text", None)

            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _answer_strategy_state_value(source: Any, key: str) -> Any:
    """Read a value from dict-like or object-like workflow state."""

    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)
'''


def replace_function(
    content: str,
    start_marker: str,
    end_marker: str | None,
    replacement: str,
    changes: list[str],
    errors: list[str],
) -> str:
    start = content.find(start_marker)
    if start == -1:
        errors.append(f"start marker not found: {start_marker}")
        return content

    if end_marker is None:
        end = len(content)
    else:
        end = content.find(end_marker, start + len(start_marker))
        if end == -1:
            errors.append(f"end marker not found after: {start_marker}")
            return content

    changes.append(f"replaced function starting with {start_marker}")
    return content[:start] + replacement + content[end:]


def main() -> int:
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    content = replace_function(
        content,
        "def _answer_strategy_unsupported_thread_spec(",
        "def _answer_strategy_query_text(",
        UNSUPPORTED_THREAD_FUNC,
        changes,
        errors,
    )
    content = replace_function(
        content,
        "def _answer_strategy_query_text(",
        None,
        QUERY_TEXT_FUNCS,
        changes,
        errors,
    )

    if not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())