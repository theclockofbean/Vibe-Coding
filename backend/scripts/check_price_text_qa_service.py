"""Check PriceTextQAService.

This script verifies the full controlled price text QA chain:
PriceParameterParser -> PriceHandler -> PriceAnswerRenderer.

It does not query the database and does not generate prices.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import PriceHandler  # noqa: E402
from app.agent.parsers import PriceParameterParser  # noqa: E402
from app.agent.renderers import PriceAnswerRenderer  # noqa: E402
from app.agent.services import PriceTextQAService  # noqa: E402


@dataclass(frozen=True)
class PriceTextQAServiceCheckCase:
    """One price text QA service check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_is_price_intent: bool
    expected_handoff_required: bool
    expected_answer_fragment: str


def build_cases() -> list[PriceTextQAServiceCheckCase]:
    """Return deterministic service check cases."""

    return [
        PriceTextQAServiceCheckCase(
            text="SKU001 多少钱",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="已识别到 SKU：SKU001",
        ),
        PriceTextQAServiceCheckCase(
            text="sku1 单价多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="当前系统尚未接入正式价格表",
        ),
        PriceTextQAServiceCheckCase(
            text="SKU001 100个多少钱",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="已识别到采购数量：100",
        ),
        PriceTextQAServiceCheckCase(
            text="43330-39585 报价",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="已识别到 OEM 对照号：43330-39585",
        ),
        PriceTextQAServiceCheckCase(
            text="M10*1.5 批发价多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="已识别到螺纹规格：M10×1.5",
        ),
        PriceTextQAServiceCheckCase(
            text="多少钱",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="请先提供 SKU、OEM 对照号或螺纹规格",
        ),
        PriceTextQAServiceCheckCase(
            text="有没有优惠",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="当前系统尚未接入正式价格表",
        ),
        PriceTextQAServiceCheckCase(
            text="包邮吗",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="物流费用或免运条件",
        ),
        PriceTextQAServiceCheckCase(
            text="43330-39585 和 12345-67890 多少钱",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_is_price_intent=True,
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个 OEM 对照号",
        ),
        PriceTextQAServiceCheckCase(
            text="SKU001 什么规格",
            expected_parse_status="not_price_intent",
            expected_handler_status="invalid_request",
            expected_is_price_intent=False,
            expected_handoff_required=False,
            expected_answer_fragment="当前未识别为价格问题",
        ),
    ]


def build_service() -> PriceTextQAService:
    """Build PriceTextQAService."""

    return PriceTextQAService(
        parser=PriceParameterParser(),
        handler=PriceHandler(),
        renderer=PriceAnswerRenderer(),
    )


def assert_no_forbidden_price_content(answer_text: str) -> bool:
    """Check answer text contains no generated price or commitment."""

    forbidden_fragments = [
        "¥",
        "￥",
        "元",
        "折扣",
        "包邮",
        "免费发",
        "立减",
        "优惠价",
        "活动价",
        "最低价",
    ]

    for fragment in forbidden_fragments:
        if fragment in answer_text:
            print(
                "failed: answer must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def run_case(
    *,
    service: PriceTextQAService,
    case: PriceTextQAServiceCheckCase,
) -> bool:
    """Run one service check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    result = service.answer(text=case.text)
    payload = result.to_response_payload()
    answer_text = result.rendered_answer.text

    print(f"parse_status: {payload['parse_status']}")
    print(f"is_price_intent: {payload['is_price_intent']}")
    print(f"price_query_type: {payload['price_query_type']}")
    print(f"product_reference_type: {payload['product_reference_type']}")
    print(f"product_reference_value: {payload['product_reference_value']}")
    print(f"quantity: {payload['quantity']}")
    print(f"handler_status: {payload['handler_status']}")
    print(f"handoff_required: {payload['handoff_required']}")
    print("answer_text:")
    print(answer_text)

    if payload["parse_status"] != case.expected_parse_status:
        print(
            "failed: expected parse_status "
            f"{case.expected_parse_status!r}, got {payload['parse_status']!r}"
        )
        return False

    if payload["handler_status"] != case.expected_handler_status:
        print(
            "failed: expected handler_status "
            f"{case.expected_handler_status!r}, got {payload['handler_status']!r}"
        )
        return False

    if payload["is_price_intent"] != case.expected_is_price_intent:
        print(
            "failed: expected is_price_intent "
            f"{case.expected_is_price_intent!r}, "
            f"got {payload['is_price_intent']!r}"
        )
        return False

    if payload["handoff_required"] != case.expected_handoff_required:
        print(
            "failed: expected handoff_required "
            f"{case.expected_handoff_required!r}, "
            f"got {payload['handoff_required']!r}"
        )
        return False

    if case.expected_answer_fragment not in answer_text:
        print(
            "failed: expected answer_text to contain "
            f"{case.expected_answer_fragment!r}"
        )
        return False

    return assert_no_forbidden_price_content(answer_text)


def main() -> int:
    """Run price text QA service checks."""

    service = build_service()
    cases = build_cases()

    results = [
        run_case(
            service=service,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("price text QA service check failed")
        return 1

    print("price text QA service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())