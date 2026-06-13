"""Fix unified KB router fitment priority."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routing/unified_kb_router.py"


def main() -> int:
    """Patch unified KB router fitment priority."""

    print("=" * 80)
    print("fixing unified KB router fitment priority")

    if not ROUTER_FILE.exists():
        pprint({"error": f"missing router file: {ROUTER_FILE}"})
        return 1

    content = ROUTER_FILE.read_text(encoding="utf-8")
    original = content

    if "SPEC_FITMENT_SIGNALS" not in content:
        content = content.replace(
            '''SPEC_HIGH_RISK_SIGNALS: Final[tuple[str, ...]] = (
    "万能适配",
    "通用适配",
    "一定适配",
    "保证适配",
    "百分百适配",
    "全部车型",
)
''',
            '''SPEC_HIGH_RISK_SIGNALS: Final[tuple[str, ...]] = (
    "万能适配",
    "通用适配",
    "一定适配",
    "保证适配",
    "百分百适配",
    "全部车型",
)

SPEC_FITMENT_SIGNALS: Final[tuple[str, ...]] = (
    "适配",
    "车型",
    "车款",
    "兼容",
    "装车",
    "能不能用",
)
''',
        )

    old_select = '''    if has_any_signal(matched_signals=matched_signals, signals=SPEC_HIGH_RISK_SIGNALS):
        return "spec"

    if matched_signals["price"]:
        return "price"

    if matched_signals["logistics"]:
        return "logistics"

    if matched_signals["spec"]:
        return "spec"
'''

    new_select = '''    if has_any_signal(matched_signals=matched_signals, signals=SPEC_HIGH_RISK_SIGNALS):
        return "spec"

    if has_any_signal(matched_signals=matched_signals, signals=SPEC_FITMENT_SIGNALS):
        return "spec"

    if matched_signals["price"]:
        return "price"

    if matched_signals["logistics"]:
        return "logistics"

    if matched_signals["spec"]:
        return "spec"
'''

    if old_select not in content:
        pprint({"error": "select_module anchor not found"})
        return 1

    content = content.replace(old_select, new_select, 1)

    if content == original:
        pprint({"router_file": str(ROUTER_FILE), "changed": False})
        return 0

    ROUTER_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "router_file": str(ROUTER_FILE),
            "changed": True,
            "fix": "fitment signals now route to spec before logistics",
        }
    )

    print("unified KB router fitment priority fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())