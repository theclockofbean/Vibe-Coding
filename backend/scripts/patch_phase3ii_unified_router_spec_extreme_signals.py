"""Add spec extreme-query signals to UnifiedIntentRouter."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routers/unified_intent_router.py"

OLD_BLOCK: Final[str] = '''        "杆长",
        "球径",
        "锥度",
'''

NEW_BLOCK: Final[str] = '''        "杆长",
        "最长",
        "最大杆长",
        "最长杆长",
        "杆长最大",
        "杆长最长",
        "杆最长",
        "球径",
        "最大球径",
        "球径最大",
        "球头最大",
        "锥度",
'''


def main() -> int:
    """Patch router signals."""

    content = ROUTER_FILE.read_text(encoding="utf-8")
    original = content
    errors: list[str] = []
    changes: list[str] = []

    if NEW_BLOCK in content:
        changes.append("spec extreme-query signals already present")
    elif OLD_BLOCK in content:
        content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
        changes.append("added spec extreme-query signals")
    else:
        errors.append("spec signal anchor not found")

    if content != original and not errors:
        ROUTER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())