"""Check LogisticsAnswerRenderer.

This script verifies controlled logistics rendering.

It reads products from the local database through LogisticsHandler, but does
not call an LLM, calculate shipping fees, promise delivery time, promise free
shipping, promise carriers, or write data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import LogisticsHandler  # noqa: E402
from app.agent.parsers import LogisticsParameterParser  # noqa: E402
from app.agent.renderers import LogisticsAnswerRenderer  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402


@dataclass(frozen=True)
class LogisticsRendererCheckCase:
    """One logistics renderer check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_answer_fragments: tuple[str, ...]
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[LogisticsRendererCheckCase]:
    """Return deterministic renderer check cases."""

    return [
        LogisticsRendererCheckCase(
            text="SKU001 几天发货",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "查到 SKU001",
                "当前备货状态为现货",
                "发货周期约 2 天",
                "该时间仅表示发货周期，不代表到货时间",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 有现货吗",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "查到 SKU001",
                "当前备货状态为现货",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 运费多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "当前系统不能自动承诺具体物流费用",
                "请转人工确认",
            ),
            forbidden_answer_fragments=(
                "运费是",
                "邮费是",
                "元",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 包邮吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "当前系统不能自动承诺免运",
                "请转人工确认",
            ),
            forbidden_answer_fragments=(
                "可以包邮",
                "支持包邮",
                "默认包邮",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 发到杭州几天",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "已识别到收货地区：杭州",
                "当前系统不能自动承诺具体到货时间",
                "请转人工确认",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 发什么快递",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "当前系统不能自动承诺指定快递",
                "请转人工确认",
            ),
        ),
        LogisticsRendererCheckCase(
            text="物流单号呢",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "请先提供 SKU、OEM 对照号或螺纹规格",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 能加急吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "当前系统不能自动承诺加急",
                "请转人工确认",
            ),
            forbidden_answer_fragments=(
                "今天一定发",
                "马上发",
                "可以加急",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU999 几天发货",
            expected_parse_status="parsed",
            expected_handler_status="not_found",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "暂未查到 SKU999 对应的物流基础信息",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 和 SKU003 分别几天发货",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "识别到多个 SKU",
            ),
        ),
        LogisticsRendererCheckCase(
            text="SKU001 多少钱",
            expected_parse_status="not_logistics_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "当前未识别为物流问题",
            ),
        ),
    ]


def build_handler() -> LogisticsHandler:
    """Build LogisticsHandler with database-backed repository."""

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        return LogisticsHandler(product_repository=product_repository)


def assert_no_global_forbidden_fragments(answer_text: str) -> bool:
    """Check answer text contains no unsupported logistics commitment."""

    forbidden_fragments = [
        "保证到",
        "一定到",
        "今天到",
        "明天到",
        "准时到",
        "几天送达",
        "可以包邮",
        "支持包邮",
        "默认包邮",
        "免运费",
        "运费是",
        "邮费是",
        "快递费是",
        "发顺丰",
        "发圆通",
        "发中通",
        "今天一定发",
        "可以加急",
        "赔付",
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
    parser: LogisticsParameterParser,
    handler: LogisticsHandler,
    renderer: LogisticsAnswerRenderer,
    case: LogisticsRendererCheckCase,
) -> bool:
    """Run one renderer check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    handler_result = handler.handle(parsed_query)
    rendered_answer = renderer.render(handler_result)
    answer_text = rendered_answer.text

    print(f"parse_status: {parsed_query.status}")
    print(f"handler_status: {handler_result.status}")
    print(f"handoff_required: {rendered_answer.handoff_required}")
    print("answer_text:")
    print(answer_text)

    if parsed_query.status != case.expected_parse_status:
        print(
            "failed: expected parse_status "
            f"{case.expected_parse_status!r}, got {parsed_query.status!r}"
        )
        return False

    if handler_result.status != case.expected_handler_status:
        print(
            "failed: expected handler_status "
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

    for fragment in case.expected_answer_fragments:
        if fragment not in answer_text:
            print(
                "failed: expected answer to contain "
                f"{fragment!r}"
            )
            return False

    for fragment in case.forbidden_answer_fragments:
        if fragment in answer_text:
            print(
                "failed: answer must not contain case forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return assert_no_global_forbidden_fragments(answer_text)


def main() -> int:
    """Run logistics renderer checks."""

    parser = LogisticsParameterParser()
    handler = build_handler()
    renderer = LogisticsAnswerRenderer()
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
        print("logistics answer renderer check failed")
        return 1

    print("logistics answer renderer check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())