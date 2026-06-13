"""Check Quality API boundary cases.

This script verifies POST /api/v1/quality/query boundary behavior.

It does not call an LLM, promise durability, promise rust resistance, promise
scratch resistance, promise warranty, promise returns/exchanges, promise
compensation, judge quality responsibility, or write data.
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

from app.main import app  # noqa: E402


@dataclass(frozen=True)
class HTTPBoundaryCase:
    """One HTTP validation boundary case."""

    name: str
    payload: dict[str, Any]
    expected_status_code: int


@dataclass(frozen=True)
class SemanticBoundaryCase:
    """One semantic quality boundary case."""

    name: str
    text: str
    expected_http_status_code: int
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_answer_fragments: tuple[str, ...]
    expected_quality_query_type: str | None = None
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
    ]


def build_semantic_boundary_cases() -> list[SemanticBoundaryCase]:
    """Return semantic boundary cases."""

    return [
        SemanticBoundaryCase(
            name="multiple_sku_ambiguous",
            text="SKU001 和 SKU003 哪个质量更好",
            expected_http_status_code=200,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_quality_query_type="general_quality",
            expected_answer_fragments=(
                "识别到多个 SKU",
                "一次只能确认一个产品",
            ),
        ),
        SemanticBoundaryCase(
            name="multiple_oem_ambiguous",
            text="43330-39585 和 12345-67890 哪个更耐用",
            expected_http_status_code=200,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_quality_query_type="durability",
            expected_answer_fragments=(
                "识别到多个 OEM 对照号",
                "一次只能确认一个产品",
            ),
        ),
        SemanticBoundaryCase(
            name="multiple_thread_specs_ambiguous",
            text="M8x1.25 和 M10x1.5 哪个不容易坏",
            expected_http_status_code=200,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_quality_query_type="durability",
            expected_answer_fragments=(
                "识别到多个螺纹规格",
                "一次只能确认一个产品范围",
            ),
            forbidden_answer_fragments=(
                "不会坏",
                "保证耐用",
            ),
        ),
        SemanticBoundaryCase(
            name="not_quality_intent",
            text="SKU001 几天发货",
            expected_http_status_code=200,
            expected_parse_status="not_quality_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_quality_query_type=None,
            expected_answer_fragments=(
                "当前未识别为质量问题",
            ),
        ),
        SemanticBoundaryCase(
            name="missing_product_reference",
            text="质量问题能赔吗",
            expected_http_status_code=200,
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_quality_query_type="compensation",
            expected_answer_fragments=(
                "缺少产品引用",
                "请先提供 SKU、OEM 对照号或螺纹规格",
            ),
            forbidden_answer_fragments=(
                "一定赔",
                "一定补发",
            ),
        ),
        SemanticBoundaryCase(
            name="not_found",
            text="SKU999 什么材质",
            expected_http_status_code=200,
            expected_parse_status="parsed",
            expected_handler_status="not_found",
            expected_handoff_required=True,
            expected_quality_query_type="material",
            expected_answer_fragments=(
                "暂未查到 SKU999 对应的质量基础信息",
                "请核对 SKU、OEM 对照号或螺纹规格",
            ),
        ),
        SemanticBoundaryCase(
            name="warranty_handoff",
            text="SKU001 质保多久",
            expected_http_status_code=200,
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_quality_query_type="warranty",
            expected_answer_fragments=(
                "不能自动承诺质保期限",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "一年质保",
                "终身质保",
            ),
        ),
        SemanticBoundaryCase(
            name="return_exchange_handoff",
            text="SKU001 不合适能退吗",
            expected_http_status_code=200,
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_quality_query_type="return_exchange",
            expected_answer_fragments=(
                "不能自动承诺一定可退或一定可换",
                "请转人工进一步确认",
            ),
            forbidden_answer_fragments=(
                "一定能退",
                "一定能换",
            ),
        ),
        SemanticBoundaryCase(
            name="defect_issue_handoff",
            text="SKU001 收到有划痕",
            expected_http_status_code=200,
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_quality_query_type="defect_issue",
            expected_answer_fragments=(
                "不能直接判断责任",
                "请提供订单、图片、视频和安装信息",
            ),
            forbidden_answer_fragments=(
                "一定赔",
                "一定补发",
            ),
        ),
    ]


def assert_no_global_forbidden_fragments(answer_text: str) -> bool:
    """Check answer text contains no unsupported quality commitments."""

    forbidden_fragments = [
        "绝对不会坏",
        "保证不会坏",
        "不会坏",
        "保证不生锈",
        "绝对不生锈",
        "保证不掉漆",
        "绝对不掉漆",
        "保证耐用",
        "保证耐用几年",
        "能用几年",
        "终身质保",
        "一年质保",
        "两年质保",
        "三年质保",
        "七天无理由",
        "一定能退",
        "一定能换",
        "一定赔",
        "一定补发",
        "质量问题一定赔",
        "装不上一定负责",
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
        "/api/v1/quality/query",
        json=case.payload,
    )

    print(f"status_code: {response.status_code}")
    try:
        pprint(response.json())
    except ValueError:
        print(response.text)

    if response.status_code != case.expected_status_code:
        print(
            "failed: expected HTTP status "
            f"{case.expected_status_code}, got {response.status_code}"
        )
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
        "/api/v1/quality/query",
        json={
            "text": case.text,
            "limit": 5,
        },
    )

    if response.status_code != case.expected_http_status_code:
        print(
            "failed: expected HTTP status "
            f"{case.expected_http_status_code}, got {response.status_code}"
        )
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    checks: list[tuple[str, object | None, object | None]] = [
        ("parse_status", case.expected_parse_status, payload["parse_status"]),
        ("handler_status", case.expected_handler_status, payload["handler_status"]),
        (
            "handoff_required",
            case.expected_handoff_required,
            payload["handoff_required"],
        ),
        (
            "quality_query_type",
            case.expected_quality_query_type,
            payload["quality_query_type"],
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
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
    """Run quality API boundary checks."""

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
        print("quality API boundary check failed")
        return 1

    print("quality API boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())