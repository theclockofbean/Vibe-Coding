"""Fix unified KB router so SKU/OEM-only spec signals do not override Quality."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routing/unified_kb_router.py"


def main() -> int:
    """Patch unified KB router quality priority for identifier-only spec signals."""

    print("=" * 80)
    print("fixing router identifier-only spec signal priority")

    if not ROUTER_FILE.exists():
        pprint({"error": f"missing router file: {ROUTER_FILE}"})
        return 1

    content = ROUTER_FILE.read_text(encoding="utf-8")
    original = content

    old_block = '''    if matched_signals["logistics"]:
        return "logistics"

    if matched_signals["spec"]:
        return "spec"

    if matched_signals["quality"]:
        return "quality"
'''

    new_block = '''    if matched_signals["logistics"]:
        return "logistics"

    if (
        matched_signals["quality"]
        and is_identifier_only_spec_signal(matched_signals.get("spec", []))
    ):
        return "quality"

    if matched_signals["spec"]:
        return "spec"

    if matched_signals["quality"]:
        return "quality"
'''

    if old_block not in content:
        pprint({"error": "select_module identifier-only quality anchor not found"})
        return 1

    content = content.replace(old_block, new_block, 1)

    if content == original:
        pprint({"router_file": str(ROUTER_FILE), "changed": False})
        return 0

    ROUTER_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "router_file": str(ROUTER_FILE),
            "changed": True,
            "fix": "quality wins when spec signal is only SKU/OEM identifier noise",
        }
    )

    print("router identifier-only quality priority fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())