"""Analyze Phase 3-I-I 50-case eval failures by root cause."""

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

SAFE_NEGATION_FRAGMENTS: Final[tuple[str, ...]] = (
    "不能直接给出报价",
    "无法直接报价",
    "不能直接报价",
    "不能直接给出最低价",
    "无法承诺最低价",
    "不能承诺最低价",
    "不能保证最低价",
    "不能直接给出承诺价格",
)

SPEC_PARSER_FAILURE_MARKERS: Final[tuple[str, ...]] = (
    "no SKU ID, OEM reference number, or thread spec was found",
    "当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
)

HANDOFF_KEYWORDS: Final[tuple[str, ...]] = (
    "转人工",
    "人工确认",
    "联系客服",
    "人工处理",
    "人工客服",
)


def main() -> int:
    """Analyze failure causes."""

    print("=" * 80)
    print("analyzing Phase 3-I-I 50-case failure causes")

    if not REPORT_FILE.exists():
        print(f"missing report file: {REPORT_FILE}")
        return 1

    data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    summary: dict[str, Any] = data["summary"]
    results: list[dict[str, Any]] = data["results"]

    categories = {
        "system_bug_spec_parser": [],
        "evaluator_false_positive_price_negation": [],
        "capability_gap_escalation": [],
        "risk_gate_not_triggered": [],
        "module_mismatch": [],
        "content_recall_or_knowledge_gap": [],
        "other": [],
    }

    for item in results:
        classify_item(item=item, categories=categories)

    compact = {
        "summary": summary,
        "root_cause_counts": {
            key: len(value)
            for key, value in categories.items()
        },
        "category_counts": Counter(str(item.get("category")) for item in results),
        "scenario_counts": Counter(str(item.get("scenario_type")) for item in results),
        "top_cases_by_root_cause": {
            key: [
                {
                    "case_id": item["case_id"],
                    "category": item["category"],
                    "scenario_type": item["scenario_type"],
                    "expected_module": item["expected_module"],
                    "selected_module": item["selected_module"],
                    "answer_strategy_mode": item["answer_strategy_mode"],
                    "failure_reasons": item["failure_reasons"][:5],
                    "final_response_preview": str(item["final_response"])[:220],
                }
                for item in value[:8]
            ]
            for key, value in categories.items()
        },
    }

    pprint(compact)

    print("Phase 3-I-I 50-case failure cause analysis completed")
    return 0


def classify_item(
    *,
    item: dict[str, Any],
    categories: dict[str, list[dict[str, Any]]],
) -> None:
    """Classify one failed case."""

    reasons = [str(reason) for reason in item.get("failure_reasons", [])]
    final_response = str(item.get("final_response") or "")
    expected_module = str(item.get("expected_module") or "")
    selected_module = str(item.get("selected_module") or "")

    matched = False

    if expected_module == "spec" and any(
        marker in final_response
        for marker in SPEC_PARSER_FAILURE_MARKERS
    ):
        categories["system_bug_spec_parser"].append(item)
        matched = True

    if expected_module == "escalation":
        categories["capability_gap_escalation"].append(item)
        matched = True

    if any("price compliance violation" in reason for reason in reasons):
        if any(fragment in final_response for fragment in SAFE_NEGATION_FRAGMENTS):
            categories["evaluator_false_positive_price_negation"].append(item)
            matched = True

    if any("forbidden fragments leaked" in reason for reason in reasons):
        if any(fragment in final_response for fragment in SAFE_NEGATION_FRAGMENTS):
            categories["evaluator_false_positive_price_negation"].append(item)
            matched = True

    if any("risk case was not gated" in reason for reason in reasons):
        categories["risk_gate_not_triggered"].append(item)
        matched = True

    if expected_module and selected_module and expected_module != selected_module:
        categories["module_mismatch"].append(item)
        matched = True

    if any("missing must_contain" in reason for reason in reasons):
        categories["content_recall_or_knowledge_gap"].append(item)
        matched = True

    if not matched and reasons:
        categories["other"].append(item)


if __name__ == "__main__":
    raise SystemExit(main())