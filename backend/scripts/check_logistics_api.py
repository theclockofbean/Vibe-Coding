"""Check Logistics API.

This script verifies POST /api/v1/logistics/query.

It does not call an LLM, calculate shipping fees, promise delivery time,
promise free shipping, promise carriers, promise expedite, or write data.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

from fastapi.testclient import TestClient

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


@dataclass(frozen=True)
class LogisticsAPICheckCase:
    """One logistics API check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_query_type: str | None
    expected_answer_fragments: tuple[str, ...]
    expected_destination_text: str | None = None
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[LogisticsAPICheckCase]:
    """Return deterministic logistics API check cases."""

    return [
        LogisticsAPICheckCase(
            text="SKU001 几天发货",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_query_type="shipping_time",
            expected_answer_fragments=(
                "发货周期约 2 天",
                "不代表到货时间",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 有现货吗",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_query_type="stock_status",
            expected_answer_fragments=(
                "当前备货状态为现货",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 运费多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="shipping_fee",
            expected_answer_fragments=(
                "不能自动承诺具体物流费用",
                "请转人工确认",
            ),
            forbidden_answer_fragments=(
                "运费是",
                "邮费是",
                "元",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 包邮吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="free_shipping",
            expected_answer_fragments=(
                "不能自动承诺免运",
                "请转人工确认",
            ),
            forbidden_answer_fragments=(
                "可以包邮",
                "支持包邮",
                "默认包邮",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 发到杭州几天",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="delivery_time",
            expected_destination_text="杭州",
            expected_answer_fragments=(
                "已识别到收货地区：杭州",
                "不能自动承诺具体到货时间",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 发什么快递",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="carrier",
            expected_answer_fragments=(
                "不能自动承诺指定快递",
                "请转人工确认",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 能加急吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="expedite",
            expected_answer_fragments=(
                "不能自动承诺加急",
                "请转人工确认",
            ),
        ),
        LogisticsAPICheckCase(
            text="物流单号呢",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_query_type="tracking",
            expected_answer_fragments=(
                "请先提供 SKU、OEM 对照号或螺纹规格",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU999 几天发货",
            expected_parse_status="parsed",
            expected_handler_status="not_found",
            expected_handoff_required=True,
            expected_query_type="shipping_time",
            expected_answer_fragments=(
                "暂未查到 SKU999 对应的物流基础信息",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 和 SKU003 分别几天发货",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_query_type="shipping_time",
            expected_answer_fragments=(
                "识别到多个 SKU",
            ),
        ),
        LogisticsAPICheckCase(
            text="SKU001 多少钱",
            expected_parse_status="not_logistics_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_query_type=None,
            expected_answer_fragments=(
                "当前未识别为物流问题",
            ),
        ),
    ]


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
                "failed: answer_text must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def run_case(
    *,
    client: TestClient,
    case: LogisticsAPICheckCase,
) -> bool:
    """Run one API check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    response = client.post(
        "/api/v1/logistics/query",
        json={
            "text": case.text,
            "limit": 5,
        },
    )

    if response.status_code != 200:
        print(f"failed: expected status 200, got {response.status_code}")
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
            "logistics_query_type",
            case.expected_query_type,
            payload["logistics_query_type"],
        ),
        (
            "destination_text",
            case.expected_destination_text,
            payload["destination_text"],
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
    """Run logistics API checks."""

    client = TestClient(app)
    cases = build_cases()

    results = [
        run_case(
            client=client,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("logistics API check failed")
        return 1

    print("logistics API check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())