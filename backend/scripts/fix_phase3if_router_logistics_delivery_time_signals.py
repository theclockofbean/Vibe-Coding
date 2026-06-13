"""Fix unified KB router logistics delivery-time signals."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routing/unified_kb_router.py"


def main() -> int:
    """Patch logistics delivery-time signals."""

    print("=" * 80)
    print("fixing router logistics delivery-time signals")

    if not ROUTER_FILE.exists():
        pprint({"error": f"missing router file: {ROUTER_FILE}"})
        return 1

    content = ROUTER_FILE.read_text(encoding="utf-8")
    original = content

    old_block = '''    "到货",
    "明天到",
    "多久能到",
    "运费",
'''

    new_block = '''    "到货",
    "明天到",
    "多久能到",
    "几天能到",
    "几天到",
    "大概几天",
    "发到",
    "发浙江",
    "发广东",
    "发江苏",
    "发上海",
    "发北京",
    "运费",
'''

    if old_block not in content:
        pprint({"error": "logistics signal anchor not found"})
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
            "fix": "added delivery-time and destination-shipping logistics signals",
        }
    )

    print("router logistics delivery-time signal fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())