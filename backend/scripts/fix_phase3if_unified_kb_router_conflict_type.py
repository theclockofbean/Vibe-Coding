"""Fix Phase 3-I-F unified KB router conflict type logic."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routing/unified_kb_router.py"


def main() -> int:
    """Patch unified KB router."""

    print("=" * 80)
    print("fixing unified KB router conflict type logic")

    if not ROUTER_FILE.exists():
        pprint({"error": f"missing router file: {ROUTER_FILE}"})
        return 1

    content = ROUTER_FILE.read_text(encoding="utf-8")
    original = content

    content = content.replace(
        '''    "发货",
    "今天发",
    "当天发",
''',
        '''    "发货",
    "能发",
    "今天发",
    "今天能发",
    "当天发",
    "当天能发",
'''
    )

    content = content.replace(
        '''    conflict_type = build_conflict_type(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
    )
''',
        '''    conflict_type = build_conflict_type(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        matched_signals=matched_signals,
    )
'''
    )

    old_function = '''def build_conflict_type(
    *,
    selected_module: str | None,
    candidate_modules: list[str],
) -> str | None:
    """Build selected-module-first conflict type."""

    if selected_module is None:
        return None

    other_modules = [
        module
        for module in candidate_modules
        if module != selected_module
    ]

    if not other_modules:
        return selected_module

    return f"{selected_module}_{other_modules[0]}"
'''

    new_function = '''def build_conflict_type(
    *,
    selected_module: str | None,
    candidate_modules: list[str],
    matched_signals: dict[str, list[str]],
) -> str | None:
    """Build selected-module-first conflict type."""

    if selected_module is None:
        return None

    secondary_module = select_conflict_secondary_module(
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        matched_signals=matched_signals,
    )

    if secondary_module is None:
        return selected_module

    return f"{selected_module}_{secondary_module}"


def select_conflict_secondary_module(
    *,
    selected_module: str,
    candidate_modules: list[str],
    matched_signals: dict[str, list[str]],
) -> str | None:
    """Select most meaningful secondary module for conflict type."""

    other_modules = [
        module
        for module in candidate_modules
        if module != selected_module
    ]

    if not other_modules:
        return None

    if "quality" in other_modules and is_identifier_only_spec_signal(
        matched_signals.get("spec", [])
    ):
        return "quality"

    if selected_module == "price":
        for module in ("quality", "logistics", "spec"):
            if module in other_modules:
                return module

    if selected_module == "logistics":
        for module in ("quality", "spec", "price"):
            if module in other_modules:
                return module

    if selected_module == "spec":
        for module in ("logistics", "quality", "price"):
            if module in other_modules:
                return module

    return other_modules[0]


def is_identifier_only_spec_signal(
    spec_signals: list[str],
) -> bool:
    """Return whether spec match is only SKU/OEM identifier noise."""

    if not spec_signals:
        return False

    identifier_signals = {"sku", "oem"}

    return set(spec_signals) <= identifier_signals
'''

    if old_function not in content:
        pprint({"error": "build_conflict_type function anchor not found"})
        return 1

    content = content.replace(old_function, new_function, 1)

    if content == original:
        pprint({"router_file": str(ROUTER_FILE), "changed": False})
        return 0

    ROUTER_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "router_file": str(ROUTER_FILE),
            "changed": True,
            "fixes": [
                "added logistics signals for 今天能发 / 能发",
                "added secondary conflict module selection",
                "treated SKU/OEM-only spec signal as identifier noise",
            ],
        }
    )

    print("unified KB router conflict type fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())