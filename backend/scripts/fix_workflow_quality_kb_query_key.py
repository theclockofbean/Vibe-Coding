"""Fix Quality KB retriever query extraction keys."""

from __future__ import annotations

from pathlib import Path


WORKFLOW_FILE = Path("app/agent/workflow.py")


def fix_query_keys() -> None:
    """Add user_text to real Quality KB query extraction."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    old = '    for key in ("current_message", "user_message", "query", "message"):\n'
    new = (
        '    for key in (\n'
        '        "user_text",\n'
        '        "current_message",\n'
        '        "user_message",\n'
        '        "query",\n'
        '        "message",\n'
        '    ):\n'
    )

    if old not in content and '"user_text",' in content:
        print("workflow.py already includes user_text query key")
        return

    if old not in content:
        raise RuntimeError("target query key line not found in workflow.py")

    content = content.replace(old, new, 1)
    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print("workflow.py query extraction fixed")


if __name__ == "__main__":
    fix_query_keys()