# ruff: noqa: E402,I001
"""Check Unified Agent API boundary cases.

This script verifies POST /api/v1/agent/query boundary behavior.

It does not call an LLM, promise prices, promise logistics, promise quality,
promise warranty, promise returns/exchanges, promise compensation, or write
data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from fastapi.testclient import TestClient

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


ENDPOINT: Final[str] = "/api/v1/agent/query"


@dataclass(frozen=True)
class HTTPBoundaryCase:
    """One HTTP validation boundary case."""

    name: str
    payload: dict[str, Any]
    expected_status_code: int


@dataclass(frozen=True)
class SemanticBoundaryCase:
    """One semantic unified agent boundary case."""

    name: str
    text: str
    expected_status_code: int
    expected_selected_module: str | None
    expected_route_status: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_module_payload_present: bool
    expected_answer_fragments: tuple[str, ...]
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_http_boundary_cases() -> list[HTTPBoundaryCase]:
    """Return HTTP-level boundary cases."""

    return [
        HTTPBoundaryCase(
            name="missing_text",
            payload={"limit": 5},
            expected_status_code=422,
        ),
        HTTPBoundaryCase(
            name="empty_text",
            payload={"text": "", "limit": 5},
            expected_status_code=422,
        ),
        HTTPBoundaryCase(
            name="blank_text",
            payload={"text": "   ", "limit": 5},
            expected_status_code=422,
        ),
        HTTPBoundaryCase(
            name="too_long_text",
            payload={"text": "质" * 501, "limit": 5},
            expected_status_code=422,
        ),
        HTTPBoundaryCase(
            name="limit_too_small",
            payload={"text": "SKU001 什么材质", "limit": 0},
            expected_status_code=422,
        ),
        HTTPBoundaryCase(
            name="limit_too_large",
            payload={"text": "SKU001 什么材质", "limit": 21},
            expected_status_code=422,
        ),
        HTTPBoundaryCase(
            name="missing_limit_uses_default",
            payload={"text": "SKU001 什么材质"},
            expected_status_code=200,
        ),
    ]


def build_semantic_boundary_cases() -> list[SemanticBoundaryCase]:
    """Return semantic boundary cases."""

    return [
        SemanticBoundaryCase(
            name="spec_material_default",
            text="SKU001 什么材质",
            expected_status_code=200,
            expected_selected_module="spec",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "材质",
            ),
        ),
        SemanticBoundaryCase(
            name="spec_thread",
            text="SKU001 螺纹是多少",
            expected_status_code=200,
            expected_selected_module="spec",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "螺纹规格",
            ),
        ),
        SemanticBoundaryCase(
            name="price_handoff",
            text="SKU001 多少钱",
            expected_status_code=200,
            expected_selected_module="price",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "不能直接给出报价",
                "转人工确认",
            ),
            forbidden_answer_fragments=(
                "保证最低价",
                "最低价给你",
            ),
        ),
        SemanticBoundaryCase(
            name="logistics_shipping_time",
            text="SKU001 几天发货",
            expected_status_code=200,
            expected_selected_module="logistics",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "发货周期",
                "不代表到货时间",
            ),
            forbidden_answer_fragments=(
                "保证到货",
                "今天一定发",
                "一定包邮",
            ),
        ),
        SemanticBoundaryCase(
            name="quality_rust_handoff",
            text="SKU001 会不会生锈",
            expected_status_code=200,
            expected_selected_module="quality",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "不能自动承诺不生锈",
            ),
            forbidden_answer_fragments=(
                "保证不生锈",
                "绝对不生锈",
            ),
        ),
        SemanticBoundaryCase(
            name="quality_material_performance",
            text="SKU001 这个材质耐用吗",
            expected_status_code=200,
            expected_selected_module="quality",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "不能自动承诺产品寿命",
            ),
            forbidden_answer_fragments=(
                "保证耐用",
                "能用几年",
            ),
        ),
        SemanticBoundaryCase(
            name="quality_return_exchange",
            text="SKU001 掉漆能退吗",
            expected_status_code=200,
            expected_selected_module="quality",
            expected_route_status="routed",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_module_payload_present=True,
            expected_answer_fragments=(
                "SKU001",
                "不能自动承诺一定可退或一定可换",
            ),
            forbidden_answer_fragments=(
                "一定能退",
                "一定能换",
            ),
        ),
        SemanticBoundaryCase(
            name="ambiguous_multi_module",
            text="SKU001 多少钱，几天发货，质量怎么样",
            expected_status_code=200,
            expected_selected_module=None,
            expected_route_status="ambiguous",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_module_payload_present=False,
            expected_answer_fragments=(
                "识别到多个业务问题",
                "请拆分为规格、价格、物流或质量中的一个问题",
            ),
        ),
        SemanticBoundaryCase(
            name="unknown",
            text="你好",
            expected_status_code=200,
            expected_selected_module=None,
            expected_route_status="unknown",
            expected_parse_status="unknown",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_module_payload_present=False,
            expected_answer_fragments=(
                "当前未识别到可处理的业务问题",
            ),
        ),
    ]


def assert_no_global_forbidden_fragments(answer_text: str) -> bool:
    """Check answer text contains no unsupported business commitments."""

    forbidden_fragments = [
        "保证最低价",
        "最低价给你",
        "一定包邮",
        "保证到货",
        "今天一定发",
        "保证不坏",
        "保证不生锈",
        "保证不掉漆",
        "保证耐用",
        "能用几年",
        "一年质保",
        "终身质保",
        "七天无理由",
        "一定能退",
        "一定能换",
        "一定赔",
        "一定补发",
        "质量很好",
        "放心用",
        "完全没问题",
    ]

    for fragment in forbidden_fragments:
        if fragment in answer_text:
            print(
                "failed: answer_text must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def run_http_boundary_case(
    *,
    client: TestClient,
    case: HTTPBoundaryCase,
) -> bool:
    """Run one HTTP boundary case."""

    print("=" * 80)
    print(f"http boundary: {case.name}")

    response = client.post(
        ENDPOINT,
        json=case.payload,
    )

    print(f"status_code: {response.status_code}")

    try:
        payload = response.json()
        pprint(payload)
    except ValueError:
        print(response.text)

    if response.status_code != case.expected_status_code:
        print(
            "failed: expected HTTP status "
            f"{case.expected_status_code}, got {response.status_code}"
        )
        return False

    if response.status_code == 200:
        payload = response.json()

        if "answer_text" not in payload:
            print("failed: successful response missing answer_text")
            return False

        if not assert_no_global_forbidden_fragments(str(payload["answer_text"])):
            return False

    return True


def run_semantic_boundary_case(
    *,
    client: TestClient,
    case: SemanticBoundaryCase,
) -> bool:
    """Run one semantic boundary case."""

    print("=" * 80)
    print(f"semantic boundary: {case.name}")
    print(f"text: {case.text}")

    response = client.post(
        ENDPOINT,
        json={
            "text": case.text,
            "limit": 5,
        },
    )

    if response.status_code != case.expected_status_code:
        print(
            "failed: expected HTTP status "
            f"{case.expected_status_code}, got {response.status_code}"
        )
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    checks: list[tuple[str, object | None, object | None]] = [
        (
            "selected_module",
            case.expected_selected_module,
            payload["selected_module"],
        ),
        ("route_status", case.expected_route_status, payload["route_status"]),
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
                "failed: answer_text must not contain case forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return assert_no_global_forbidden_fragments(answer_text)


def main() -> int:
    """Run unified agent API boundary checks."""

    client = TestClient(app)

    http_results = [
        run_http_boundary_case(
            client=client,
            case=case,
        )
        for case in build_http_boundary_cases()
    ]

    semantic_results = [
        run_semantic_boundary_case(
            client=client,
            case=case,
        )
        for case in build_semantic_boundary_cases()
    ]

    print("=" * 80)

    if not all(http_results + semantic_results):
        print("unified agent API boundary check failed")
        return 1

    print("unified agent API boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())