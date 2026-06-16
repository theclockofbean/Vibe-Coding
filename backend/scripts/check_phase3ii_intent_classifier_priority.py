# ruff: noqa: E402,I001
"""Check Phase 3-I-I intent classifier priority routing."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.intent_classifier import IntentClassificationResult
from app.agent.llm.intent_classifier import classify_intent_by_keywords
from app.agent.llm.intent_classifier import _resolve_llm_intent_with_local_cues


P0_EXPECTATIONS: Final[tuple[dict[str, str], ...]] = (
    {
        "case_id": "TC_SPEC_004",
        "query": "SKU004不锈钢子弹头 给我报一下全部参数",
        "expected": "spec",
    },
    {
        "case_id": "TC_SPEC_007",
        "query": "你们最长的杆是多少 哪款",
        "expected": "spec",
    },
    {
        "case_id": "TC_SPEC_011",
        "query": "你们钛合金材质的球头有哪些款",
        "expected": "spec",
    },
    {
        "case_id": "TC_LOGI_002",
        "query": "能发顺丰吗 我在浙江 要补多少钱",
        "expected": "logistics",
    },
    {
        "case_id": "TC_LOGI_003",
        "query": "发顺丰去新疆多少差价",
        "expected": "logistics",
    },
    {
        "case_id": "TC_PRICE_002",
        "query": "我要100个SKU006钛合金球头 批发价多少",
        "expected": "price",
    },
    {
        "case_id": "TC_PRICE_007",
        "query": "需要1000个SKU020 报个价",
        "expected": "price",
    },
    {
        "case_id": "TC_PRICE_008",
        "query": "我老客户了 给我个实在价",
        "expected": "price",
    },
    {
        "case_id": "TC_QUAL_001",
        "query": "你们的是原厂件吗",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_003",
        "query": "钛合金和铝合金球头哪个更好 有什么区别",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_004",
        "query": "SKU003真皮包覆的会不会掉色或者发霉",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_005",
        "query": "夜光球头用久了夜光会不会褪色",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_008",
        "query": "你们有没有质检报告或者认证",
        "expected": "quality",
    },
    {
        "case_id": "TC_ESCA_001",
        "query": "你们是骗子 东西根本用不了 我要差评投诉",
        "expected": "escalation",
    },
    {
        "case_id": "TC_ESCA_002",
        "query": "我想定制一批带我们公司LOGO的球头 500个",
        "expected": "escalation",
    },
    {
        "case_id": "TC_ESCA_003",
        "query": "我按照你说的装上去结果球头裂了 你们赔不赔",
        "expected": "escalation",
    },
)


def main() -> int:
    """Check classifier priority routing."""

    print("=" * 80)
    print("checking Phase 3-I-I intent classifier priority routing")

    errors: list[str] = []
    rows: list[dict[str, Any]] = []

    for item in P0_EXPECTATIONS:
        query = item["query"]
        expected = item["expected"]
        result = classify_intent_by_keywords(query)

        rows.append(
            {
                "case_id": item["case_id"],
                "expected": expected,
                "actual": result.intent,
                "confidence": result.confidence,
                "reason": result.reason,
                "metadata": result.metadata,
            }
        )

        if result.intent != expected:
            errors.append(
                f"{item['case_id']}: expected {expected}, got {result.intent}"
            )

        if result.metadata.get("phase3ii_priority_router") is not True:
            errors.append(f"{item['case_id']}: priority router metadata missing")

    resolver_result = check_resolver_priority_override(errors=errors)

    pprint(
        {
            "rows": rows,
            "resolver_result": resolver_result,
            "errors": errors,
        }
    )

    if errors:
        print("Phase 3-I-I intent classifier priority routing check failed")
        return 1

    print("Phase 3-I-I intent classifier priority routing check passed")
    return 0


def check_resolver_priority_override(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check LLM resolver lets local priority override parsed LLM intent."""

    parsed = IntentClassificationResult(
        intent="spec",
        confidence=0.79,
        reason="mock llm spec",
        used_llm=True,
        raw_content='{"intent":"spec","confidence":0.79}',
    )

    resolved = _resolve_llm_intent_with_local_cues(
        user_text="需要1000个SKU020 报个价",
        parsed=parsed,
    )

    if resolved.intent != "price":
        errors.append(f"resolver expected price, got {resolved.intent}")

    if resolved.metadata.get("resolver") != "phase3ii_priority_local_cue_resolution":
        errors.append("resolver priority metadata missing")

    return {
        "input_llm_intent": parsed.intent,
        "resolved_intent": resolved.intent,
        "metadata": resolved.metadata,
    }


if __name__ == "__main__":
    raise SystemExit(main())