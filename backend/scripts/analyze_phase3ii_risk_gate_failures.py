"""Analyze Phase 3-I-I 50-case risk gate failures."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from pprint import pprint
from typing import Any, Final


REPORT_FILE: Final[Path] = Path(
    "D:/Projects/ai-knowledge-agent-platform/logs/evaluation/"
    "phase3ii_real_llm_50_case_eval_report.json"
)

RISK_REASON_MARKERS: Final[tuple[str, ...]] = (
    "expected handoff was not triggered",
    "risk case was not gated",
)

RISK_SIGNAL_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "fitment_or_installation": (
        "安装",
        "适配",
        "车型",
        "怎么装",
        "能不能装",
        "装不上",
        "装坏",
        "损坏",
    ),
    "price_or_discount": (
        "报价",
        "价格",
        "批发",
        "优惠",
        "便宜",
        "最低",
        "老客户",
        "1000",
        "500",
    ),
    "logistics_fee_or_exception": (
        "运费",
        "补差",
        "破损",
        "压变形",
        "退货",
        "换货",
        "港澳台",
        "澳门",
        "新疆",
        "顺丰",
    ),
    "quality_claim_or_certification": (
        "原厂",
        "OEM正品",
        "质检",
        "认证",
        "检测",
        "报告",
        "寿命",
        "耐用",
        "生锈",
        "开裂",
        "褪色",
    ),
    "complaint_or_escalation": (
        "投诉",
        "客服",
        "人工",
        "赔",
        "退款",
        "方案",
        "定制",
        "LOGO",
        "售后",
    ),
}


def main() -> int:
    """Analyze latest risk gate failures."""

    print("=" * 80)
    print("analyzing Phase 3-I-I risk gate failures")

    if not REPORT_FILE.exists():
        print(f"missing report file: {REPORT_FILE}")
        return 1

    data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = data["results"]

    failures = [
        item
        for item in results
        if has_risk_gate_failure(item)
    ]

    grouped = group_failures(failures)
    compact_cases = [compact_case(item) for item in failures]

    output = {
        "risk_gate_failure_count": len(failures),
        "by_category": Counter(str(item.get("category")) for item in failures),
        "by_scenario_type": Counter(str(item.get("scenario_type")) for item in failures),
        "by_expected_module": Counter(str(item.get("expected_module")) for item in failures),
        "by_selected_module": Counter(str(item.get("selected_module")) for item in failures),
        "by_signal_group": {
            key: len(value)
            for key, value in grouped.items()
        },
        "cases_by_signal_group": {
            key: [compact_case(item) for item in value[:10]]
            for key, value in grouped.items()
        },
        "all_risk_gate_failure_cases": compact_cases,
    }

    pprint(output)

    print("Phase 3-I-I risk gate failure analysis completed")
    return 0


def has_risk_gate_failure(
    item: dict[str, Any],
) -> bool:
    """Return whether a case has risk gate blocker."""

    reasons = [str(reason) for reason in item.get("failure_reasons", [])]

    return any(
        marker in reason
        for marker in RISK_REASON_MARKERS
        for reason in reasons
    )


def group_failures(
    failures: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group failures by risk signal family."""

    grouped: dict[str, list[dict[str, Any]]] = {
        key: []
        for key in RISK_SIGNAL_GROUPS
    }
    grouped["unclassified"] = []

    for item in failures:
        text = build_case_text(item)
        matched = False

        for group_name, keywords in RISK_SIGNAL_GROUPS.items():
            if any(keyword in text for keyword in keywords):
                grouped[group_name].append(item)
                matched = True

        if not matched:
            grouped["unclassified"].append(item)

    return grouped


def build_case_text(
    item: dict[str, Any],
) -> str:
    """Build text used for signal matching."""

    parts = [
        str(item.get("case_id") or ""),
        str(item.get("query") or ""),
        str(item.get("category") or ""),
        str(item.get("scenario_type") or ""),
        str(item.get("expected_module") or ""),
        str(item.get("selected_module") or ""),
        str(item.get("answer_strategy_mode") or ""),
        str(item.get("final_response") or ""),
        " ".join(str(reason) for reason in item.get("failure_reasons", [])),
    ]

    return "\n".join(parts)


def compact_case(
    item: dict[str, Any],
) -> dict[str, Any]:
    """Return compact case record."""

    return {
        "case_id": item.get("case_id"),
        "category": item.get("category"),
        "scenario_type": item.get("scenario_type"),
        "expected_module": item.get("expected_module"),
        "selected_module": item.get("selected_module"),
        "answer_strategy_mode": item.get("answer_strategy_mode"),
        "handoff_required": item.get("handoff_required"),
        "answer_handoff_required": item.get("answer_handoff_required"),
        "answer_safety_blocked": item.get("answer_safety_blocked"),
        "render_safety_blocked": item.get("render_safety_blocked"),
        "failure_reasons": item.get("failure_reasons", [])[:5],
        "query": item.get("query"),
        "final_response_preview": str(item.get("final_response") or "")[:260],
    }


if __name__ == "__main__":
    raise SystemExit(main())