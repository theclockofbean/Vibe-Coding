"""Local demo for the specification query chain.

Flow:
ProductRepository -> SpecQueryService -> SpecHandler -> SpecAnswerRenderer

This script only reads from PostgreSQL. It does not call an LLM and does not
modify database data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import SpecHandler, SpecHandlerInput  # noqa: E402
from app.agent.renderers import SpecAnswerRenderer  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


@dataclass(frozen=True)
class DemoCase:
    """One local demo case."""

    name: str
    handler_input: SpecHandlerInput
    expected_status: str
    expected_text_fragment: str


def build_demo_cases() -> list[DemoCase]:
    """Return deterministic demo cases."""

    return [
        DemoCase(
            name="按 SKU 查询单个产品",
            handler_input=SpecHandlerInput(
                query_type="sku_id",
                query_value="sku001",
            ),
            expected_status="success",
            expected_text_fragment="SKU001",
        ),
        DemoCase(
            name="按螺纹规格查询多个产品",
            handler_input=SpecHandlerInput(
                query_type="thread_spec",
                query_value="M8x1.25",
                limit=3,
            ),
            expected_status="success",
            expected_text_fragment="共查到 3 个匹配产品",
        ),
        DemoCase(
            name="按 OEM 对照号查询",
            handler_input=SpecHandlerInput(
                query_type="oem_reference_number",
                query_value="43330-39585",
            ),
            expected_status="success",
            expected_text_fragment="SKU001",
        ),
        DemoCase(
            name="按螺纹直径和螺距查询",
            handler_input=SpecHandlerInput(
                query_type="thread_dimensions",
                diameter_mm="8",
                pitch_mm="1.25",
                limit=3,
            ),
            expected_status="success",
            expected_text_fragment="共查到 3 个匹配产品",
        ),
        DemoCase(
            name="未命中 SKU",
            handler_input=SpecHandlerInput(
                query_type="sku_id",
                query_value="SKU999",
            ),
            expected_status="not_found",
            expected_text_fragment="没有在当前产品资料中查到",
        ),
        DemoCase(
            name="非法规格参数",
            handler_input=SpecHandlerInput(
                query_type="thread_dimensions",
                diameter_mm="abc",
                pitch_mm="1.25",
            ),
            expected_status="invalid_request",
            expected_text_fragment="规格查询参数不完整或格式不正确",
        ),
    ]


def run_demo_case(
    *,
    handler: SpecHandler,
    renderer: SpecAnswerRenderer,
    demo_case: DemoCase,
) -> bool:
    """Run one demo case and return whether it passed."""

    handler_result = handler.handle(demo_case.handler_input)
    rendered_answer = renderer.render(handler_result)

    print("=" * 80)
    print(f"case: {demo_case.name}")
    print(f"input: {demo_case.handler_input}")
    print(f"handler_status: {handler_result.status}")
    print(f"matched_count: {handler_result.matched_count}")
    print(f"handoff_required: {rendered_answer.handoff_required}")
    print("answer:")
    print(rendered_answer.text)
    print("source_references:")
    print(rendered_answer.source_references)

    if handler_result.status != demo_case.expected_status:
        print(
            "case failed: expected status "
            f"{demo_case.expected_status!r}, got {handler_result.status!r}"
        )
        return False

    if demo_case.expected_text_fragment not in rendered_answer.text:
        print(
            "case failed: expected answer to contain "
            f"{demo_case.expected_text_fragment!r}"
        )
        return False

    if "价格" in rendered_answer.text:
        print("case failed: spec demo answer must not mention price")
        return False

    return True


def main() -> int:
    """Run the local specification chain demo."""

    session_factory = get_session_factory()
    demo_cases = build_demo_cases()

    with session_factory() as session:
        repository = ProductRepository(session)
        service = SpecQueryService(repository)
        handler = SpecHandler(service)
        renderer = SpecAnswerRenderer()

        results = [
            run_demo_case(
                handler=handler,
                renderer=renderer,
                demo_case=demo_case,
            )
            for demo_case in demo_cases
        ]

    print("=" * 80)

    if not all(results):
        print("spec chain demo failed")
        return 1

    print("spec chain demo passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())