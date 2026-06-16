"""Patch Phase 3-I-I intent classifier priority routing."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CLASSIFIER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/llm/intent_classifier.py"


HELPER_BLOCK: Final[str] = '''
def _classify_phase3ii_priority_intent(
    text: str,
) -> IntentClassificationResult | None:
    """Return high-priority business intent for Phase 3-I-I routing.

    These rules are deterministic overrides for short customer service queries
    where SKU/material words can otherwise steal the route from price,
    logistics, quality, or escalation.
    """

    def has_any(fragments: tuple[str, ...]) -> bool:
        return any(fragment in text for fragment in fragments)

    if has_any(
        (
            "投诉",
            "差评",
            "骗子",
            "赔不赔",
            "赔付",
            "赔",
            "定制",
            "logo",
            "安装损坏",
            "装上去结果",
            "球头裂",
        )
    ):
        return IntentClassificationResult(
            intent="escalation",
            confidence=0.9,
            reason="Phase 3-I-I 高优先级路由命中 escalation 线索。",
            used_llm=False,
            metadata={
                "phase3ii_priority_router": True,
                "matched_intent": "escalation",
            },
        )

    if has_any(
        (
            "顺丰",
            "新疆",
            "澳门",
            "港澳台",
            "运费",
            "差价",
            "补多少钱",
            "补多少",
            "发顺丰",
        )
    ):
        return IntentClassificationResult(
            intent="logistics",
            confidence=0.88,
            reason="Phase 3-I-I 高优先级路由命中 logistics 线索。",
            used_llm=False,
            metadata={
                "phase3ii_priority_router": True,
                "matched_intent": "logistics",
            },
        )

    if has_any(
        (
            "报个价",
            "报价",
            "批发价",
            "批发",
            "实在价",
            "老客户",
            "多少钱",
            "价格",
            "单价",
            "折扣",
            "采购价",
            "成交价",
        )
    ):
        return IntentClassificationResult(
            intent="price",
            confidence=0.88,
            reason="Phase 3-I-I 高优先级路由命中 price 线索。",
            used_llm=False,
            metadata={
                "phase3ii_priority_router": True,
                "matched_intent": "price",
            },
        )

    if has_any(
        (
            "原厂",
            "oem正品",
            "质检",
            "质检报告",
            "认证",
            "认证资料",
            "检测字段",
            "检测依据",
            "哪个更好",
            "有什么区别",
            "区别",
            "会不会",
            "掉色",
            "发霉",
            "褪色",
            "夜光",
            "蓄光",
            "生锈",
        )
    ):
        return IntentClassificationResult(
            intent="quality",
            confidence=0.86,
            reason="Phase 3-I-I 高优先级路由命中 quality 线索。",
            used_llm=False,
            metadata={
                "phase3ii_priority_router": True,
                "matched_intent": "quality",
            },
        )

    if has_any(
        (
            "全部参数",
            "有哪些款",
            "哪些款",
            "哪款",
            "最长",
            "最长的杆",
            "杆是多少",
            "螺纹",
            "杆长",
            "球径",
            "锥度",
            "规格",
            "尺寸",
        )
    ):
        return IntentClassificationResult(
            intent="spec",
            confidence=0.86,
            reason="Phase 3-I-I 高优先级路由命中 spec 线索。",
            used_llm=False,
            metadata={
                "phase3ii_priority_router": True,
                "matched_intent": "spec",
            },
        )

    return None
'''


PRIORITY_CALL: Final[str] = '''    priority_result = _classify_phase3ii_priority_intent(text)
    if priority_result is not None:
        return priority_result

'''


RESOLVER_BLOCK: Final[str] = '''    if (
        local.metadata.get("phase3ii_priority_router") is True
        and local.intent != parsed.intent
    ):
        return IntentClassificationResult(
            intent=local.intent,
            confidence=max(local.confidence, min(parsed.confidence, 0.88)),
            reason=(
                "Phase 3-I-I 本地高优先级业务线索覆盖 LLM 意图。"
                f"原始 LLM 意图：{parsed.intent}；原始原因：{parsed.reason}"
            ),
            used_llm=True,
            is_valid=True,
            fallback_reason=None,
            raw_content=parsed.raw_content,
            metadata={
                "resolver": "phase3ii_priority_local_cue_resolution",
                "original_llm_intent": parsed.intent,
                "original_llm_confidence": parsed.confidence,
                "local_intent": local.intent,
                "local_confidence": local.confidence,
                "local_reason": local.reason,
            },
        )

'''


def main() -> int:
    """Patch intent classifier priority routing."""

    print("=" * 80)
    print("patching Phase 3-I-I intent classifier priority routing")

    errors: list[str] = []
    changes: list[str] = []

    if not CLASSIFIER_FILE.exists():
        errors.append(f"missing classifier file: {CLASSIFIER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = CLASSIFIER_FILE.read_text(encoding="utf-8")
    original = content

    if "_classify_phase3ii_priority_intent" not in content:
        anchor = "\ndef classify_intent_by_keywords("
        if anchor not in content:
            errors.append("classify_intent_by_keywords anchor not found")
        else:
            content = content.replace(anchor, HELPER_BLOCK + "\n" + anchor, 1)
            changes.append("inserted phase3ii priority classifier helper")
    else:
        changes.append("priority classifier helper already present")

    old_call_anchor = "    text = user_text.strip().lower()\n\n    keyword_rules:"
    if PRIORITY_CALL.strip() not in content:
        if old_call_anchor not in content:
            errors.append("priority call insertion anchor not found")
        else:
            content = content.replace(
                "    text = user_text.strip().lower()\n\n",
                "    text = user_text.strip().lower()\n\n" + PRIORITY_CALL,
                1,
            )
            changes.append("inserted priority classifier call")
    else:
        changes.append("priority classifier call already present")

    resolver_anchor = "    local = classify_intent_by_keywords(user_text)\n\n"
    if "phase3ii_priority_local_cue_resolution" not in content:
        if resolver_anchor not in content:
            errors.append("resolver local classifier anchor not found")
        else:
            content = content.replace(
                resolver_anchor,
                resolver_anchor + RESOLVER_BLOCK,
                1,
            )
            changes.append("inserted LLM resolver priority override")
    else:
        changes.append("LLM resolver priority override already present")

    if content != original and not errors:
        CLASSIFIER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I intent classifier priority patch failed")
        return 1

    print("Phase 3-I-I intent classifier priority patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())