# ruff: noqa: E402,I001
"""Check UnifiedTextQAService."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.services import UnifiedTextQAService
from app.core.database import get_session_factory
from app.repositories import ProductRepository


@dataclass(frozen=True)
class UnifiedTextQACheckCase:
    """One unified text QA service check case."""

    text: str
    expected_route_status: str
    expected_selected_module: str | None
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_answer_fragments: tuple[str, ...]
    expected_module_payload_present: bool
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[UnifiedTextQACheckCase]:
    """Return deterministic unified text QA service cases."""

    return [
        UnifiedTextQACheckCase(
            text="SKU001 螺纹是多少",
            expected_route_status="routed",
            expected_selected_module="spec",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "SKU001",
                "螺纹规格",
            ),
            expected_module_payload_present=True,
        ),
        UnifiedTextQACheckCase(
            text="SKU001 多少钱",
            expected_route_status="routed",
            expected_selected_module="price",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "SKU001",
                "不能直接给出报价",
                "转人工确认",
            ),
            expected_module_payload_present=True,
        ),
        UnifiedTextQACheckCase(
            text="SKU001 几天发货",
            expected_route_status="routed",
            expected_selected_module="logistics",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "SKU001",
                "发货周期",
                "不代表到货时间",
            ),
            expected_module_payload_present=True,
            forbidden_answer_fragments=(
                "保证到",
                "可以包邮",
                "免运费",
            ),
        ),
        UnifiedTextQACheckCase(
            text="SKU001 会不会生锈",
            expected_route_status="routed",
            expected_selected_module="quality",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_answer_fragments=(
                "SKU001",
                "不能自动承诺不生锈",
                "请转人工进一步确认",
            ),
            expected_module_payload_present=True,
            forbidden_answer_fragments=(
                "保证不生锈",
                "绝对不生锈",
            ),
        ),
        UnifiedTextQACheckCase(
            text="SKU001 什么材质",
            expected_route_status="routed",
            expected_selected_module="spec",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "SKU001",
                "材质",
            ),
            expected_module_payload_present=True,
        ),
        UnifiedTextQACheckCase(
            text="SKU001 多少钱，几天发货，质量怎么样",
            expected_route_status="ambiguous",
            expected_selected_module=None,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "识别到多个业务问题",
                "请拆分为规格、价格、物流或质量中的一个问题",
            ),
            expected_module_payload_present=False,
        ),
        UnifiedTextQACheckCase(
            text="你好",
            expected_route_status="unknown",
            expected_selected_module=None,
            expected_parse_status="unknown",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "当前未识别到可处理的业务问题",
            ),
            expected_module_payload_present=False,
        ),
        UnifiedTextQACheckCase(
            text="   ",
            expected_route_status="invalid_request",
            expected_selected_module=None,
            expected_parse_status="invalid_request",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_answer_fragments=(
                "请求内容无效",
            ),
            expected_module_payload_present=False,
        ),
    ]


def run_case(
    *,
    service: UnifiedTextQAService,
    case: UnifiedTextQACheckCase,
) -> bool:
    """Run one service check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    result = service.answer(text=case.text)
    payload = result.to_response_payload()
    pprint(payload)

    checks: list[tuple[str, object | None, object | None]] = [
        ("route_status", case.expected_route_status, payload["route_status"]),
        (
            "selected_module",
            case.expected_selected_module,
            payload["selected_module"],
        ),
        ("parse_status", case.expected_parse_status, payload["parse_status"]),
        (
            "handler_status",
            case.expected_handler_status,
            payload["handler_status"],
        ),
        (
            "handoff_required",
            case.expected_handoff_required,
            payload["handoff_required"],
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    module_payload = payload["module_payload"]

    if case.expected_module_payload_present and not isinstance(module_payload, dict):
        print("failed: module_payload expected to be a dict")
        return False

    if not case.expected_module_payload_present and module_payload is not None:
        print("failed: module_payload expected to be None")
        return False

    answer_text = str(payload["answer_text"])

    for fragment in case.expected_answer_fragments:
        if fragment not in answer_text:
            print(
                "failed: expected answer_text to contain "
                f"{fragment!r}"
            )
            return False

    for fragment in case.forbidden_answer_fragments:
        if fragment in answer_text:
            print(
                "failed: answer_text must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def main() -> int:
    """Run unified text QA service checks."""

    session_factory = get_session_factory()
    cases = build_cases()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        service = UnifiedTextQAService(
            product_repository=product_repository,
        )

        results = [
            run_case(
                service=service,
                case=case,
            )
            for case in cases
        ]

    print("=" * 80)

    if not all(results):
        print("unified text QA service check failed")
        return 1

    print("unified text QA service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())