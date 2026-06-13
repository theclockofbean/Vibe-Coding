"""Check SpecTextQAService.

This script verifies the centralized text QA service without starting FastAPI.
It only reads from PostgreSQL and does not modify data.
"""

from __future__ import annotations

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
from app.agent.services import SpecTextQAService  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


@dataclass(frozen=True)
class TextQAServiceCheckCase:
    """One text QA service check case."""

    text: str
    expected_parse_status: str
    expected_query_type: str | None
    expected_answer_fragment: str


def build_cases() -> list[TextQAServiceCheckCase]:
    """Return deterministic service check cases."""

    return [
        TextQAServiceCheckCase(
            text="帮我查一下 SKU001 的规格",
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_answer_fragment="查到 SKU001",
        ),
        TextQAServiceCheckCase(
            text="SKU001 和 SKU003 都是什么规格",
            expected_parse_status="parsed",
            expected_query_type="sku_ids",
            expected_answer_fragment="共查到 2 个匹配产品",
        ),
        TextQAServiceCheckCase(
            text="M10*1.5 有哪些",
            expected_parse_status="parsed",
            expected_query_type="thread_spec",
            expected_answer_fragment="共查到",
        ),
        TextQAServiceCheckCase(
            text="帮我查 43330-39585 和 12345-67890",
            expected_parse_status="ambiguous",
            expected_query_type=None,
            expected_answer_fragment="识别到多个 OEM 对照号",
        ),
        TextQAServiceCheckCase(
            text="你好，能介绍一下吗",
            expected_parse_status="not_supported",
            expected_query_type=None,
            expected_answer_fragment="当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
        ),
    ]


def build_service(repository: ProductRepository) -> SpecTextQAService:
    """Build SpecTextQAService."""

    spec_query_service = SpecQueryService(repository)
    handler = SpecHandler(spec_query_service)

    return SpecTextQAService(
        parser=SpecParameterParser(),
        handler=handler,
        renderer=SpecAnswerRenderer(),
    )


def run_case(
    *,
    service: SpecTextQAService,
    case: TextQAServiceCheckCase,
) -> bool:
    """Run one service check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    result = service.answer(
        text=case.text,
        limit=5,
    )
    payload = result.to_response_payload()
    answer_text = result.rendered_answer.text

    print(f"parse_status: {payload['parse_status']}")
    print(f"query_type: {payload['query_type']}")
    print(f"query_value: {payload['query_value']}")
    print("answer_text:")
    print(answer_text)

    if payload["parse_status"] != case.expected_parse_status:
        print(
            "failed: expected parse_status "
            f"{case.expected_parse_status!r}, got {payload['parse_status']!r}"
        )
        return False

    if payload["query_type"] != case.expected_query_type:
        print(
            "failed: expected query_type "
            f"{case.expected_query_type!r}, got {payload['query_type']!r}"
        )
        return False

    if case.expected_answer_fragment not in answer_text:
        print(
            "failed: expected answer_text to contain "
            f"{case.expected_answer_fragment!r}"
        )
        return False

    if "价格" in answer_text:
        print("failed: spec text QA answer must not mention price")
        return False

    if "æ" in answer_text or "Ã" in answer_text:
        print("failed: response appears to contain mojibake")
        return False

    return True


def main() -> int:
    """Run SpecTextQAService checks."""

    session_factory = get_session_factory()
    cases = build_cases()

    with session_factory() as session:
        repository = ProductRepository(session)
        service = build_service(repository)

        results = [
            run_case(
                service=service,
                case=case,
            )
            for case in cases
        ]

    print("=" * 80)

    if not all(results):
        print("spec text QA service check failed")
        return 1

    print("spec text QA service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())