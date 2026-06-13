"""Check PriceAnswerRenderer.

This script verifies controlled price responses.
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


@dataclass(frozen=True)
class PriceRendererCheckCase:
    """One price renderer check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_answer_fragment: str


def build_cases() -> list[PriceRendererCheckCase]:
    """Return deterministic renderer check cases."""

    return [
        PriceRendererCheckCase(
            text="SKU001 多少钱",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="已识别到 SKU：SKU001",
        ),
        PriceRendererCheckCase(
            text="sku1 单价多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="当前系统尚未接入正式价格表",
        ),
        PriceRendererCheckCase(
            text="SKU001 100个多少钱",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="已识别到采购数量：100",
        ),
        PriceRendererCheckCase(
            text="43330-39585 报价",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="已识别到 OEM 对照号：43330-39585",
        ),
        PriceRendererCheckCase(
            text="M10*1.5 批发价多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="已识别到螺纹规格：M10×1.5",
        ),
        PriceRendererCheckCase(
            text="多少钱",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="请先提供 SKU、OEM 对照号或螺纹规格",
        ),
        PriceRendererCheckCase(
            text="有没有优惠",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="当前系统尚未接入正式价格表",
        ),
        PriceRendererCheckCase(
            text="包邮吗",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragment="物流费用或免运条件",
        ),
        PriceRendererCheckCase(
            text="43330-39585 和 12345-67890 多少钱",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个 OEM 对照号",
        ),
        PriceRendererCheckCase(
            text="M8x1.25 和 M10x1.5 多少钱",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个螺纹规格",
        ),
        PriceRendererCheckCase(
            text="SKU001 和 SKU003 分别多少钱",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个 SKU",
        ),
        PriceRendererCheckCase(
            text="SKU001 什么规格",
            expected_parse_status="not_price_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragment="当前未识别为价格问题",
        ),
    ]


def assert_no_forbidden_price_content(answer_text: str) -> bool:
    """Check that answer text contains no generated price or promise."""

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
    parser: PriceParameterParser,
    handler: PriceHandler,
    renderer: PriceAnswerRenderer,
    case: PriceRendererCheckCase,
) -> bool:
    """Run one renderer check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    handler_result = handler.handle(parsed_query)
    rendered_answer = renderer.render(handler_result)

    print(f"parse_status: {parsed_query.status}")
    print(f"handler_status: {handler_result.status}")
    print(f"handoff_required: {rendered_answer.handoff_required}")
    print("answer_text:")
    print(rendered_answer.text)

    if parsed_query.status != case.expected_parse_status:
        print(
            "failed: expected parse status "
            f"{case.expected_parse_status!r}, got {parsed_query.status!r}"
        )
        return False

    if handler_result.status != case.expected_handler_status:
        print(
            "failed: expected handler status "
            f"{case.expected_handler_status!r}, got {handler_result.status!r}"
        )
        return False

    if rendered_answer.handoff_required != case.expected_handoff_required:
        print(
            "failed: expected handoff_required "
            f"{case.expected_handoff_required!r}, "
            f"got {rendered_answer.handoff_required!r}"
        )
        return False

    if case.expected_answer_fragment not in rendered_answer.text:
        print(
            "failed: expected answer to contain "
            f"{case.expected_answer_fragment!r}"
        )
        return False

    return assert_no_forbidden_price_content(rendered_answer.text)


def main() -> int:
    """Run price renderer checks."""

    parser = PriceParameterParser()
    handler = PriceHandler()
    renderer = PriceAnswerRenderer()
    cases = build_cases()

    results = [
        run_case(
            parser=parser,
            handler=handler,
            renderer=renderer,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("price answer renderer check failed")
        return 1

    print("price answer renderer check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())