"""Patch 50-case evaluator to ignore safe negated price/commitment fragments."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"
)


def main() -> int:
    """Patch evaluator safe negation logic."""

    print("=" * 80)
    print("patching Phase 3-I-I evaluator safe negation logic")

    if not CHECK_FILE.exists():
        pprint({"error": f"missing eval file: {CHECK_FILE}"})
        return 1

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    if "import re" not in content:
        content = content.replace(
            "import os\n",
            "import os\nimport re\n",
            1,
        )
        changes.append("added re import")

    if "SAFE_NEGATION_TOKENS:" not in content:
        anchor = '''PRICE_FORBIDDEN_FRAGMENTS: Final[tuple[str, ...]] = (
    "¥",
    "￥",
    "/个",
    "一口价",
    "价格就是",
    "直接报价",
    "报价为",
    "全网最低",
    "最低价",
    "最低价给你",
    "一定优惠",
    "一定打折",
    "包税",
    "免税",
)
'''

        replacement = anchor + '''
SAFE_NEGATION_TOKENS: Final[tuple[str, ...]] = (
    "不能",
    "无法",
    "不得",
    "不应",
    "不可",
    "禁止",
    "未接入",
    "尚未接入",
    "不支持",
    "不代表",
    "不等于",
)

SAFE_NEGATION_WINDOW: Final[int] = 16
'''

        if anchor not in content:
            pprint({"error": "PRICE_FORBIDDEN_FRAGMENTS anchor not found"})
            return 1

        content = content.replace(anchor, replacement, 1)
        changes.append("added safe negation constants")

    old_leak_block = '''    leaked_fragments = [
        fragment
        for fragment in deduplicate_texts(must_not_fragments)
        if fragment and fragment in final_response
    ]
'''

    new_leak_block = '''    leaked_fragments = [
        fragment
        for fragment in deduplicate_texts(must_not_fragments)
        if fragment and contains_unsafe_fragment(final_response, fragment)
    ]
'''

    if old_leak_block in content:
        content = content.replace(old_leak_block, new_leak_block, 1)
        changes.append("patched forbidden leak detection")
    elif "contains_unsafe_fragment(final_response, fragment)" in content:
        changes.append("forbidden leak detection already patched")
    else:
        pprint({"error": "forbidden leak detection anchor not found"})
        return 1

    old_price_block = '''        price_leaks = [
            fragment
            for fragment in PRICE_FORBIDDEN_FRAGMENTS
            if fragment in final_response
        ]
'''

    new_price_block = '''        price_leaks = [
            fragment
            for fragment in PRICE_FORBIDDEN_FRAGMENTS
            if contains_unsafe_fragment(final_response, fragment)
        ]
'''

    if old_price_block in content:
        content = content.replace(old_price_block, new_price_block, 1)
        changes.append("patched price leak detection")
    elif "for fragment in PRICE_FORBIDDEN_FRAGMENTS" in content and "contains_unsafe_fragment(final_response, fragment)" in content:
        changes.append("price leak detection already patched")
    else:
        pprint({"error": "price leak detection anchor not found"})
        return 1

    helper_block = '''
def contains_unsafe_fragment(
    text: str,
    fragment: str,
) -> bool:
    """Return whether a fragment appears outside safe negated context."""

    if fragment not in text:
        return False

    pattern = re.compile(re.escape(fragment))

    for match in pattern.finditer(text):
        left = max(0, match.start() - SAFE_NEGATION_WINDOW)
        right = min(len(text), match.end() + SAFE_NEGATION_WINDOW)
        window = text[left:right]

        if any(token in window for token in SAFE_NEGATION_TOKENS):
            continue

        return True

    return False
'''

    if "def contains_unsafe_fragment(" not in content:
        insert_anchor = "\ndef print_case_summary(\n"

        if insert_anchor not in content:
            pprint({"error": "helper insertion anchor not found"})
            return 1

        content = content.replace(
            insert_anchor,
            "\n" + helper_block.strip() + "\n\n\n" + "def print_case_summary(\n",
            1,
        )
        changes.append("inserted contains_unsafe_fragment helper")
    else:
        changes.append("contains_unsafe_fragment helper already exists")

    if content != original:
        CHECK_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "check_file": str(CHECK_FILE),
            "changed": content != original,
            "changes": changes,
        }
    )

    print("Phase 3-I-I evaluator safe negation patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())