"""Check rule-based spec parameter parser and existing spec chain.

This script parses simple customer text and passes parsed parameters through:
SpecParameterParser -> SpecHandler -> SpecAnswerRenderer.
It only reads from PostgreSQL and does not modify data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import SpecHandler  # noqa: E402
from app.agent.parsers import SpecParameterParser  # noqa: E402
from app.agent.renderers import SpecAnswerRenderer  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


@dataclass(frozen=True)
class ParserCheckCase:
    """One parser check case."""

    text: str
    expected_parse_status: str
    expected_query_type: str | None
    expected_handler_status: str | None
    expected_answer_fragment: str | None


def build_cases() -> list[ParserCheckCase]:
    """Return deterministic parser check cases."""

    return [
        ParserCheckCase(
            text="帮我查一下 SKU001 的规格",
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_handler_status="success",
            expected_answer_fragment="SKU001",
        ),
        ParserCheckCase(
            text="sku1 这款杆长是多少",
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_handler_status="success",
            expected_answer_fragment="SKU001",
        ),
        ParserCheckCase(
            text="SKU001 和 SKU003 都是什么规格",
            expected_parse_status="parsed",
            expected_query_type="sku_ids",
            expected_handler_status="success",
            expected_answer_fragment="共查到 2 个匹配产品",
        ),
        ParserCheckCase(
            text="OEM 43330-39585 对应哪个球头",
            expected_parse_status="parsed",
            expected_query_type="oem_reference_number",
            expected_handler_status="success",
            expected_answer_fragment="SKU001",
        ),
        ParserCheckCase(
            text="有没有 M8x1.25 的换挡球头",
            expected_parse_status="parsed",
            expected_query_type="thread_spec",
            expected_handler_status="success",
            expected_answer_fragment="共查到",
        ),
        ParserCheckCase(
            text="M10*1.5 有哪些",
            expected_parse_status="parsed",
            expected_query_type="thread_spec",
            expected_handler_status="success",
            expected_answer_fragment="共查到",
        ),
        ParserCheckCase(
            text="SKU999 有吗",
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_handler_status="not_found",
            expected_answer_fragment="没有在当前产品资料中查到",
        ),
        ParserCheckCase(
            text="帮我查 43330-39585 和 12345-67890",
            expected_parse_status="ambiguous",
            expected_query_type=None,
            expected_handler_status=None,
            expected_answer_fragment=None,
        ),
        ParserCheckCase(
            text="你好，能介绍一下吗",
            expected_parse_status="not_supported",
            expected_query_type=None,
            expected_handler_status=None,
            expected_answer_fragment=None,
        ),
    ]


def run_case(
    *,
    parser: SpecParameterParser,
    handler: SpecHandler,
    renderer: SpecAnswerRenderer,
    case: ParserCheckCase,
) -> bool:
    """Run one parser case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text, limit=5)

    print("parsed:")
    pprint(parsed_query.to_dict())

    if parsed_query.status != case.expected_parse_status:
        print(
            "failed: expected parse status "
            f"{case.expected_parse_status!r}, got {parsed_query.status!r}"
        )
        return False

    if parsed_query.query_type != case.expected_query_type:
        print(
            "failed: expected query type "
            f"{case.expected_query_type!r}, got {parsed_query.query_type!r}"
        )
        return False

    if parsed_query.status != "parsed":
        return True

    handler_result = handler.handle(parsed_query.to_handler_input())
    rendered_answer = renderer.render(handler_result)

    print("handler_result:")
    pprint(handler_result.to_dict())

    print("answer:")
    print(rendered_answer.text)

    if handler_result.status != case.expected_handler_status:
        print(
            "failed: expected handler status "
            f"{case.expected_handler_status!r}, got {handler_result.status!r}"
        )
        return False

    if (
        case.expected_answer_fragment is not None
        and case.expected_answer_fragment not in rendered_answer.text
    ):
        print(
            "failed: answer should contain "
            f"{case.expected_answer_fragment!r}"
        )
        return False

    if "价格" in rendered_answer.text:
        print("failed: spec answer must not mention price")
        return False

    return True


def main() -> int:
    """Run parser and chain checks."""

    parser = SpecParameterParser()
    session_factory = get_session_factory()
    cases = build_cases()

    with session_factory() as session:
        repository = ProductRepository(session)
        service = SpecQueryService(repository)
        handler = SpecHandler(service)
        renderer = SpecAnswerRenderer()

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
        print("spec parameter parser check failed")
        return 1

    print("spec parameter parser check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())