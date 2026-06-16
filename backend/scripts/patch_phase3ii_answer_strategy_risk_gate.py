"""Patch Answer Strategy risk handoff gate for Phase 3-I-I."""

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
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"
STRATEGY_CONFIG_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)

HANDOFF_RISK_FRAGMENTS: Final[list[str]] = [
    # Spec / fitment / installation
    "适配",
    "车型",
    "宝马",
    "安装",
    "怎么安装",
    "怎么装",
    "装不上",
    "锥度要求",
    "有锥度吗",
    "锥度是多少",
    "锥度和螺纹",
    "锥形球头",
    "M14",
    "USB接口",
    "温控",
    # Logistics / after-sales / exception
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
    # Price / discount
    "报价",
    "报个价",
    "批发",
    "优惠",
    "便宜",
    "实在价",
    "老客户",
    "1000个",
    "500个",
    # Quality / certification / quality claim
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
    # Complaint / escalation / customization
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
    """Patch source and config for risk handoff gate."""

    print("=" * 80)
    print("patching Phase 3-I-I answer strategy risk gate")

    errors: list[str] = []
    changes: list[str] = []

    patch_answer_strategy_source(errors=errors, changes=changes)
    patch_strategy_config(errors=errors, changes=changes)
    patch_workflow_render_gate(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I answer strategy risk gate patch failed")
        return 1

    print("Phase 3-I-I answer strategy risk gate patch completed")
    return 0


def patch_answer_strategy_source(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch multimodule_answer_strategy.py."""

    if not ANSWER_STRATEGY_FILE.exists():
        errors.append(f"missing answer strategy file: {ANSWER_STRATEGY_FILE}")
        return

    content = ANSWER_STRATEGY_FILE.read_text(encoding="utf-8")
    original = content

    if 'HANDOFF_MODE: Final[str] = "handoff_required"' not in content:
        content = content.replace(
            'SAFETY_MODE: Final[str] = "safety_blocked"\n',
            (
                'SAFETY_MODE: Final[str] = "safety_blocked"\n'
                'HANDOFF_MODE: Final[str] = "handoff_required"\n'
            ),
            1,
        )
        changes.append("added HANDOFF_MODE")

    if '"risk_handoff_required"' not in content:
        content = content.replace(
            '    "shipping_fee_price_commitment_risk": "运费和价格相关内容需要人工确认。",\n',
            (
                '    "shipping_fee_price_commitment_risk": "运费和价格相关内容需要人工确认。",\n'
                '    "risk_handoff_required": (\n'
                '        "该问题涉及适配、安装、报价、物流、质量、售后、投诉或定制等需要人工确认的信息，"\n'
                '        "请转人工确认后再处理。"\n'
                '    ),\n'
            ),
            1,
        )
        changes.append("added risk_handoff_required boundary note")

    if "handoff_risk_fragments = detect_handoff_risk_fragments(" not in content:
        content = content.replace(
            "    forbidden_fragments = detect_forbidden_fragments(\n"
            "        query=query,\n"
            "        config=config,\n"
            "    )\n",
            "    forbidden_fragments = detect_forbidden_fragments(\n"
            "        query=query,\n"
            "        config=config,\n"
            "    )\n"
            "    handoff_risk_fragments = detect_handoff_risk_fragments(\n"
            "        query=query,\n"
            "        config=config,\n"
            "    )\n",
            1,
        )
        changes.append("added handoff_risk_fragments detection in decide")

    if "reason=\"risk handoff fragment detected\"" not in content:
        content = content.replace(
            "    rule = find_pair_rule(\n",
            "    if handoff_risk_fragments:\n"
            "        return build_decision(\n"
            "            mode=HANDOFF_MODE,\n"
            "            selected_module=selected_module,\n"
            "            candidate_modules=normalized_candidates,\n"
            "            boundary_note_type=\"risk_handoff_required\",\n"
            "            forbidden_fragments=[],\n"
            "            config=config,\n"
            "            reason=\"risk handoff fragment detected\",\n"
            "        )\n"
            "\n"
            "    rule = find_pair_rule(\n",
            1,
        )
        changes.append("added risk handoff decision branch")

    if "def detect_handoff_risk_fragments(" not in content:
        helper = '''

def detect_handoff_risk_fragments(
    *,
    query: str,
    config: dict[str, Any],
) -> list[str]:
    """Detect fragments that require handoff but not full safety blocking."""

    fragments = [
        str(item)
        for item in cast(list[Any], config.get("handoff_risk_fragments", []))
    ]
    normalized_query = normalize_fragment_text(query)

    matched: list[str] = []

    for fragment in fragments:
        normalized_fragment = normalize_fragment_text(fragment)

        if normalized_fragment and normalized_fragment in normalized_query:
            matched.append(fragment)

    return matched


def normalize_fragment_text(
    value: str,
) -> str:
    """Normalize text for simple fragment matching."""

    return value.strip().lower().replace(" ", "")
'''
        content = content.replace(
            "\n\ndef find_pair_rule(\n",
            helper + "\n\ndef find_pair_rule(\n",
            1,
        )
        changes.append("added detect_handoff_risk_fragments helper")

    if content == original:
        changes.append("answer strategy source already patched")
    else:
        ANSWER_STRATEGY_FILE.write_text(content, encoding="utf-8")


def patch_strategy_config(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch strategy JSON config."""

    if not STRATEGY_CONFIG_FILE.exists():
        errors.append(f"missing strategy config file: {STRATEGY_CONFIG_FILE}")
        return

    data = json.loads(STRATEGY_CONFIG_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        errors.append("strategy config root must be object")
        return

    existing = data.get("handoff_risk_fragments", [])

    if not isinstance(existing, list):
        errors.append("handoff_risk_fragments exists but is not list")
        return

    merged = list(existing)

    for fragment in HANDOFF_RISK_FRAGMENTS:
        if fragment not in merged:
            merged.append(fragment)

    data["handoff_risk_fragments"] = merged

    STRATEGY_CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    changes.append(
        f"updated handoff_risk_fragments: {len(existing)} -> {len(merged)}"
    )


def patch_workflow_render_gate(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch workflow render gate to honor answer_handoff_required."""

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        return

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    if "render_answer_strategy_handoff_required" in content:
        changes.append("workflow handoff render gate already patched")
        return

    anchor = '    if strategy_mode == "split_required":\n'

    if anchor not in content:
        errors.append("workflow split_required anchor not found")
        return

    handoff_branch = '''    if (
        metadata.get("answer_handoff_required") is True
        and metadata.get("answer_safety_blocked") is not True
    ):
        gated_output = dict(render_output)
        render_metadata = _as_dict(gated_output.get("metadata"))
        final_response = _optional_text(gated_output.get("final_response")) or ""

        handoff_note = (
            "该问题涉及需要人工确认的信息，请转人工确认后再处理。"
        )

        if handoff_note not in final_response:
            if final_response:
                final_response = final_response.rstrip() + "\\n\\n补充边界：" + handoff_note
            else:
                final_response = handoff_note

        gated_output["final_response"] = final_response
        gated_output["needs_handoff"] = True
        render_metadata["render_answer_strategy_gate_applied"] = True
        render_metadata["render_answer_strategy_handoff_required"] = True
        render_metadata["render_fallback_reason"] = "answer_strategy_handoff_required"
        gated_output["metadata"] = render_metadata

        return gated_output

'''

    content = content.replace(anchor, handoff_branch + anchor, 1)

    if content != original:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")
        changes.append("patched workflow answer_handoff_required render gate")
    else:
        errors.append("workflow render gate patch made no change")


if __name__ == "__main__":
    raise SystemExit(main())