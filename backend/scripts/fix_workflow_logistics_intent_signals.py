"""Fix Workflow logistics intent signals."""

from __future__ import annotations

from pathlib import Path


WORKFLOW_FILE = Path("app/agent/workflow.py")


def main() -> int:
    """Add missing logistics intent signal terms."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    if '"几天能到",' in content and '"能到",' in content:
        print("workflow.py already contains logistics intent signal fixes")
        return 0

    old = '''        "logistics": [
            "物流",
            "快递",
            "发货",
            "多久",
            "运费",
            "到货",
            "时效",
        ],
'''

    new = '''        "logistics": [
            "物流",
            "快递",
            "发货",
            "多久",
            "运费",
            "到货",
            "能到",
            "几天到",
            "几天能到",
            "大概几天",
            "时效",
        ],
'''

    if old not in content:
        raise RuntimeError("target logistics module_signals block not found")

    content = content.replace(old, new, 1)
    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print("workflow.py logistics intent signals fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())