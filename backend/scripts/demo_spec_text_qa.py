"""Local text demo for specification Q&A.

Flow:
customer text -> SpecTextQAService -> controlled answer.

This script only reads from PostgreSQL. It does not call an LLM and does not
modify database data.
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

from app.agent.handlers import SpecHandler  # noqa: E402
from app.agent.parsers import SpecParameterParser  # noqa: E402
from app.agent.renderers import SpecAnswerRenderer  # noqa: E402
from app.agent.services import SpecTextQAService, TextQAResult  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


@dataclass(frozen=True)
class DemoCase:
    """One demo text case."""

    text: str
    expected_fragment: str


def build_demo_cases() -> list[DemoCase]:
    """Return deterministic local demo cases."""

    return [
        DemoCase(
            text="帮我查一下 SKU001 的规格",
            expected_fragment="SKU001",
        ),
        DemoCase(
            text="sku1 这款杆长是多少",
            expected_fragment="SKU001",
        ),
        DemoCase(
            text="SKU001 和 SKU003 都是什么规格",
            expected_fragment="共查到 2 个匹配产品",
        ),
        DemoCase(
            text="有没有 M8x1.25 的换挡球头",
            expected_fragment="共查到",
        ),
        DemoCase(
            text="M10*1.5 有哪些",
            expected_fragment="共查到",
        ),
        DemoCase(
            text="OEM 43330-39585 对应哪个球头",
            expected_fragment="SKU001",
        ),
        DemoCase(
            text="SKU999 有吗",
            expected_fragment="没有在当前产品资料中查到",
        ),
        DemoCase(
            text="帮我查 43330-39585 和 12345-67890",
            expected_fragment="识别到多个 OEM 对照号",
        ),
        DemoCase(
            text="你好，能介绍一下吗",
            expected_fragment="当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
        ),
    ]


def build_spec_text_qa_service(
    repository: ProductRepository,
) -> SpecTextQAService:
    """Build local specification text QA service."""

    spec_query_service = SpecQueryService(repository)
    handler = SpecHandler(spec_query_service)

    return SpecTextQAService(
        parser=SpecParameterParser(),
        handler=handler,
        renderer=SpecAnswerRenderer(),
    )


def run_one_text(
    *,
    text: str,
    text_qa_service: SpecTextQAService,
    limit: int,
) -> TextQAResult:
    """Run and print one local text query."""

    result = text_qa_service.answer(
        text=text,
        limit=limit,
    )
    parsed_query = result.parsed_query
    rendered_answer = result.rendered_answer

    print("=" * 80)
    print(f"user_text: {text}")
    print(f"parse_status: {parsed_query.status}")
    print(f"query_type: {parsed_query.query_type}")
    print(f"query_value: {parsed_query.query_value}")
    print(f"sku_ids: {parsed_query.sku_ids}")
    print(f"warnings: {parsed_query.warnings}")
    print(f"errors: {parsed_query.errors}")
    print("answer:")
    print(rendered_answer.text)
    print(f"handoff_required: {rendered_answer.handoff_required}")
    print(f"source_references: {rendered_answer.source_references}")

    return result


def run_builtin_demo(
    *,
    text_qa_service: SpecTextQAService,
    limit: int,
) -> bool:
    """Run built-in demo cases."""

    results: list[bool] = []

    for demo_case in build_demo_cases():
        result = run_one_text(
            text=demo_case.text,
            text_qa_service=text_qa_service,
            limit=limit,
        )

        answer_text = result.rendered_answer.text
        passed = demo_case.expected_fragment in answer_text

        if "价格" in answer_text:
            print("case failed: spec answer must not mention price")
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
        description="Run local text specification Q&A demo.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Single customer text to answer.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum products returned for list queries.",
    )

    return parser.parse_args()


def main() -> int:
    """Run local text specification Q&A demo."""

    args = parse_args()

    if args.limit <= 0:
        print("limit must be positive")
        return 1

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ProductRepository(session)
        text_qa_service = build_spec_text_qa_service(repository)

        if args.text:
            run_one_text(
                text=args.text,
                text_qa_service=text_qa_service,
                limit=args.limit,
            )
            return 0

        passed = run_builtin_demo(
            text_qa_service=text_qa_service,
            limit=args.limit,
        )

    print("=" * 80)

    if not passed:
        print("spec text qa demo failed")
        return 1

    print("spec text qa demo passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())