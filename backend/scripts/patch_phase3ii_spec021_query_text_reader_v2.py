"""Expand query text reader for answer strategy handoff templates."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint


WORKFLOW_FILE = Path("app/agent/workflow.py")


OLD_KEYS = '''        "message",
    )
'''


NEW_KEYS = '''        "message",
        "input",
        "prompt",
        "request_text",
        "customer_message",
        "latest_user_message",
        "original_query",
        "original_text",
        "normalized_text",
    )
'''


OLD_MESSAGES_CHECK = '''    if isinstance(messages, list):
'''


NEW_MESSAGES_CHECK = '''    if isinstance(messages, (list, tuple)):
'''


def main() -> int:
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_KEYS in content:
        content = content.replace(OLD_KEYS, NEW_KEYS, 1)
        changes.append("expanded query text state keys")
    elif "original_query" in content:
        changes.append("query text state keys already expanded")
    else:
        errors.append("query keys anchor not found")

    if OLD_MESSAGES_CHECK in content:
        content = content.replace(OLD_MESSAGES_CHECK, NEW_MESSAGES_CHECK, 1)
        changes.append("expanded messages container types")
    elif "isinstance(messages, (list, tuple))" in content:
        changes.append("messages container types already expanded")
    else:
        errors.append("messages type anchor not found")

    if not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())