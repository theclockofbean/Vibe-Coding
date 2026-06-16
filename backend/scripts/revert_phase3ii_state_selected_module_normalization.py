"""Revert response payload selected_module normalization."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

STATE_FILE = Path("app/agent/state.py")

OLD_LINE = '''        "selected_module": _response_selected_module(state),
'''
NEW_LINE = '''        "selected_module": state.get("selected_module"),
'''


def main() -> int:
    content = STATE_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_LINE in content:
        content = content.replace(OLD_LINE, NEW_LINE, 1)
        STATE_FILE.write_text(content, encoding="utf-8")
        changes.append("restored raw selected_module in response payload")
    elif NEW_LINE in content:
        changes.append("raw selected_module already restored")
    else:
        errors.append("selected_module payload line not found")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())