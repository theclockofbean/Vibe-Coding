"""Local text demo for controlled price Q&A.

Flow:
customer text -> PriceTextQAService -> controlled answer.

This script does not query the database, call an LLM, or generate prices.
"""

from __future__ import annotations

import argparse
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
from app.agent.services import PriceTextQAResult, PriceTextQAService  # noqa: E402


@dataclass(frozen=True)
class DemoCase:
    """One demo text case."""

    text: str
    expected_fragment: str


def build_demo_cases() -> list[DemoCase]:
    """Return deterministic local demo cases."""

    return [
        DemoCase(
            text="SKU001 多少钱",
            expected_fragment="已识别到 SKU：SKU001",
        ),
        DemoCase(
            text="sku1 单价多少",
            expected_fragment="当前系统尚未接入正式价格表",
        ),
        DemoCase(
            text="SKU001 100个多少钱",
            expected_fragment="已识别到采购数量：100",
        ),
        DemoCase(
            text="43330-39585 报价",
            expected_fragment="已识别到 OEM 对照号：43330-39585",
        ),
        DemoCase(
            text="M10*1.5 批发价多少",
            expected_fragment="已识别到螺纹规格：M10×1.5",
        ),
        DemoCase(
            text="多少钱",
            expected_fragment="请先提供 SKU、OEM 对照号或螺纹规格",
        ),
        DemoCase(
            text="有没有优惠",
            expected_fragment="当前系统尚未接入正式价格表",
        ),
        DemoCase(
            text="包邮吗",
            expected_fragment="物流费用或免运条件",
        ),
        DemoCase(
            text="43330-39585 和 12345-67890 多少钱",
            expected_fragment="识别到多个 OEM 对照号",
        ),
        DemoCase(
            text="SKU001 什么规格",
            expected_fragment="当前未识别为价格问题",
        ),
    ]


def build_price_text_qa_service() -> PriceTextQAService:
    """Build local price text QA service."""

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
                "case failed: answer must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def run_one_text(
    *,
    text: str,
    service: PriceTextQAService,
) -> PriceTextQAResult:
    """Run and print one local text query."""

    result = service.answer(text=text)
    parsed_query = result.parsed_query
    handler_result = result.handler_result
    rendered_answer = result.rendered_answer

    print("=" * 80)
    print(f"user_text: {text}")
    print(f"parse_status: {parsed_query.status}")
    print(f"is_price_intent: {parsed_query.is_price_intent}")
    print(f"price_query_type: {parsed_query.price_query_type}")
    print(f"product_reference_type: {parsed_query.product_reference_type}")
    print(f"product_reference_value: {parsed_query.product_reference_value}")
    print(f"quantity: {parsed_query.quantity}")
    print(f"handler_status: {handler_result.status}")
    print(f"handoff_required: {rendered_answer.handoff_required}")
    print("answer:")
    print(rendered_answer.text)

    return result


def run_builtin_demo(service: PriceTextQAService) -> bool:
    """Run built-in demo cases."""

    results: list[bool] = []

    for demo_case in build_demo_cases():
        result = run_one_text(
            text=demo_case.text,
            service=service,
        )

        answer_text = result.rendered_answer.text
        passed = demo_case.expected_fragment in answer_text

        if not assert_no_forbidden_price_content(answer_text):
            passed = False

        if not passed:
            print(
                "case failed: expected answer to contain "
                f"{demo_case.expected_fragment!r}"
            )

        results.append(passed)

    return all(results)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run local controlled price Q&A demo.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Single customer text to answer.",
    )

    return parser.parse_args()


def main() -> int:
    """Run local controlled price Q&A demo."""

    args = parse_args()
    service = build_price_text_qa_service()

    if args.text:
        result = run_one_text(
            text=args.text,
            service=service,
        )
        answer_text = result.rendered_answer.text

        if not assert_no_forbidden_price_content(answer_text):
            return 1

        return 0

    passed = run_builtin_demo(service)

    print("=" * 80)

    if not passed:
        print("price text qa demo failed")
        return 1

    print("price text qa demo passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())