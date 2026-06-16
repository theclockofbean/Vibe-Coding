"""Reduce Answer Strategy risk gate noise and let risky split cases handoff."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

ANSWER_STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)
STRATEGY_CONFIG_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)

REMOVE_HANDOFF_FRAGMENTS: Final[set[str]] = {
    "有锥度吗",
    "锥度是多少",
    "锥度和螺纹",
    "锥形球头",
    "什么材质",
    "材质",
}

KEEP_HANDOFF_FRAGMENTS: Final[list[str]] = [
    # explicit fitment / installation risk
    "适配",
    "车型",
    "宝马",
    "安装",
    "怎么安装",
    "怎么装",
    "装不上",
    "锥度要求",
    # logistics / after-sales / exception
    "运费",
    "补差",
    "差价",
    "运费谁承担",
    "退换货",
    "退货",
    "换货",
    "外包装破损",
    "破损",
    "压变形",
    "澳门",
    "港澳台",
    "新疆",
    "顺丰",
    # price / discount
    "报价",
    "报个价",
    "批发",
    "优惠",
    "便宜",
    "实在价",
    "老客户",
    "1000个",
    "500个",
    # quality claim / certification
    "原厂",
    "OEM正品",
    "质检",
    "认证",
    "检测",
    "检测报告",
    "质检报告",
    "寿命",
    "耐用",
    "发霉",
    "开裂",
    "褪色",
    "哪个更好",
    # complaint / escalation / customization
    "投诉",
    "差评",
    "骗子",
    "客服",
    "人工",
    "售后",
    "赔",
    "退款",
    "定制",
    "LOGO",
    "方案",
]


def main() -> int:
    """Apply noise reduction patch."""

    print("=" * 80)
    print("patching Phase 3-I-I risk gate noise reduction")

    errors: list[str] = []
    changes: list[str] = []

    patch_strategy_config(errors=errors, changes=changes)
    patch_decide_order(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I risk gate noise reduction patch failed")
        return 1

    print("Phase 3-I-I risk gate noise reduction patch completed")
    return 0


def patch_strategy_config(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Remove overly broad handoff fragments."""

    if not STRATEGY_CONFIG_FILE.exists():
        errors.append(f"missing strategy config file: {STRATEGY_CONFIG_FILE}")
        return

    data = json.loads(STRATEGY_CONFIG_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        errors.append("strategy config root must be object")
        return

    current = data.get("handoff_risk_fragments", [])

    if not isinstance(current, list):
        errors.append("handoff_risk_fragments must be list")
        return

    before = [str(item) for item in current]
    merged: list[str] = []

    for item in before + KEEP_HANDOFF_FRAGMENTS:
        if item in REMOVE_HANDOFF_FRAGMENTS:
            continue
        if item not in merged:
            merged.append(item)

    data["handoff_risk_fragments"] = merged

    STRATEGY_CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    changes.append(
        "updated handoff_risk_fragments "
        f"{len(before)} -> {len(merged)}; removed={sorted(REMOVE_HANDOFF_FRAGMENTS)}"
    )


def patch_decide_order(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Move selected_module None split branch after risk branches."""

    if not ANSWER_STRATEGY_FILE.exists():
        errors.append(f"missing answer strategy file: {ANSWER_STRATEGY_FILE}")
        return

    content = ANSWER_STRATEGY_FILE.read_text(encoding="utf-8")
    original = content

    selected_none_block = '''    if selected_module is None:
        return build_decision(
            mode="split_required",
            selected_module=None,
            candidate_modules=normalized_candidates,
            boundary_note_type="none",
            forbidden_fragments=forbidden_fragments,
            config=config,
            reason="no selected module; ask user to clarify or split question",
        )

'''

    if selected_none_block not in content:
        changes.append("selected_module None block not found or already moved")
        return

    content = content.replace(selected_none_block, "", 1)

    insert_anchor = '''    rule = find_pair_rule(
'''

    moved_block = '''    if selected_module is None:
        return build_decision(
            mode="split_required",
            selected_module=None,
            candidate_modules=normalized_candidates,
            boundary_note_type="none",
            forbidden_fragments=forbidden_fragments,
            config=config,
            reason="no selected module; ask user to clarify or split question",
        )

'''

    if insert_anchor not in content:
        errors.append("rule insertion anchor not found")
        return

    content = content.replace(insert_anchor, moved_block + insert_anchor, 1)

    if content != original:
        ANSWER_STRATEGY_FILE.write_text(content, encoding="utf-8")
        changes.append("moved selected_module None split branch after risk branches")
    else:
        errors.append("answer strategy decide order patch made no change")


if __name__ == "__main__":
    raise SystemExit(main())