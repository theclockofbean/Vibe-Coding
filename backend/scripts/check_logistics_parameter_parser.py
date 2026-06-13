"""Check LogisticsParameterParser.

This script verifies deterministic logistics parameter parsing.

It does not query the database, call an LLM, calculate shipping fees,
or promise logistics outcomes.
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

from app.agent.parsers import LogisticsParameterParser  # noqa: E402


@dataclass(frozen=True)
class LogisticsParserCheckCase:
    """One logistics parser check case."""

    text: str
    expected_status: str
    expected_is_logistics_intent: bool
    expected_query_type: str | None = None
    expected_reference_type: str | None = None
    expected_reference_value: str | None = None
    expected_sku_ids: list[str] | None = None
    expected_quantity: int | None = None
    expected_destination_text: str | None = None
    expected_error_fragment: str | None = None
    expected_warning_fragment: str | None = None


def build_cases() -> list[LogisticsParserCheckCase]:
    """Return deterministic parser check cases."""

    return [
        LogisticsParserCheckCase(
            text="SKU001 几天发货",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        LogisticsParserCheckCase(
            text="sku1 有现货吗",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="stock_status",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        LogisticsParserCheckCase(
            text="SKU001 100个几天发货",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
            expected_quantity=100,
        ),
        LogisticsParserCheckCase(
            text="43330-39585 发货周期",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_reference_type="oem_reference_number",
            expected_reference_value="43330-39585",
        ),
        LogisticsParserCheckCase(
            text="M10*1.5 运费多少",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_fee",
            expected_reference_type="thread_spec",
            expected_reference_value="M10×1.5",
        ),
        LogisticsParserCheckCase(
            text="SKU001 发到杭州几天",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="delivery_time",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
            expected_destination_text="杭州",
        ),
        LogisticsParserCheckCase(
            text="M10*1.5 寄到上海运费多少",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_fee",
            expected_reference_type="thread_spec",
            expected_reference_value="M10×1.5",
            expected_destination_text="上海",
        ),
        LogisticsParserCheckCase(
            text="SKU001 发什么快递",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="carrier",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        LogisticsParserCheckCase(
            text="SKU001 能加急吗",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="expedite",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        LogisticsParserCheckCase(
            text="SKU001 包邮吗",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="free_shipping",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        LogisticsParserCheckCase(
            text="物流单号呢",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="tracking",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="几天发货",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="有现货吗",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="stock_status",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="运费多少",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_fee",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="包邮吗",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="free_shipping",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="几天到",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="delivery_time",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="SKU001 和 SKU003 分别几天发货",
            expected_status="ambiguous",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_error_fragment="multiple SKU IDs found",
        ),
        LogisticsParserCheckCase(
            text="43330-39585 和 12345-67890 运费多少",
            expected_status="ambiguous",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_fee",
            expected_error_fragment="multiple OEM reference numbers found",
        ),
        LogisticsParserCheckCase(
            text="M8x1.25 和 M10x1.5 几天发货",
            expected_status="ambiguous",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_error_fragment="multiple thread specs found",
        ),
        LogisticsParserCheckCase(
            text="SKU001 和 43330-39585 几天发货",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_reference_type="sku_id",
            expected_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
            expected_warning_fragment="SKU ID has priority over OEM reference number",
        ),
        LogisticsParserCheckCase(
            text="43330-39585 和 M8x1.25 发货周期",
            expected_status="parsed",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_reference_type="oem_reference_number",
            expected_reference_value="43330-39585",
            expected_warning_fragment="OEM reference number has priority over thread spec",
        ),
        LogisticsParserCheckCase(
            text="广东能发吗",
            expected_status="missing_product_reference",
            expected_is_logistics_intent=True,
            expected_query_type="shipping_time",
            expected_destination_text="广东",
            expected_error_fragment="missing product reference",
        ),
        LogisticsParserCheckCase(
            text="SKU001 什么规格",
            expected_status="not_logistics_intent",
            expected_is_logistics_intent=False,
        ),
        LogisticsParserCheckCase(
            text="SKU001 多少钱",
            expected_status="not_logistics_intent",
            expected_is_logistics_intent=False,
        ),
        LogisticsParserCheckCase(
            text="你好",
            expected_status="not_logistics_intent",
            expected_is_logistics_intent=False,
        ),
        LogisticsParserCheckCase(
            text="   ",
            expected_status="not_logistics_intent",
            expected_is_logistics_intent=False,
            expected_error_fragment="text must not be blank",
        ),
    ]


def run_case(
    *,
    parser: LogisticsParameterParser,
    case: LogisticsParserCheckCase,
) -> bool:
    """Run one parser check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    payload = parsed_query.to_dict()

    pprint(payload)

    checks: list[tuple[str, object | None, object | None]] = [
        ("status", case.expected_status, parsed_query.status),
        (
            "is_logistics_intent",
            case.expected_is_logistics_intent,
            parsed_query.is_logistics_intent,
        ),
        (
            "logistics_query_type",
            case.expected_query_type,
            parsed_query.logistics_query_type,
        ),
        (
            "product_reference_type",
            case.expected_reference_type,
            parsed_query.product_reference_type,
        ),
        (
            "product_reference_value",
            case.expected_reference_value,
            parsed_query.product_reference_value,
        ),
        (
            "quantity",
            case.expected_quantity,
            parsed_query.quantity,
        ),
        (
            "destination_text",
            case.expected_destination_text,
            parsed_query.destination_text,
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    if case.expected_sku_ids is not None and parsed_query.sku_ids != case.expected_sku_ids:
        print(
            "failed: sku_ids expected "
            f"{case.expected_sku_ids!r}, got {parsed_query.sku_ids!r}"
        )
        return False

    if (
        case.expected_error_fragment is not None
        and case.expected_error_fragment not in "；".join(parsed_query.errors)
    ):
        print(
            "failed: expected errors to contain "
            f"{case.expected_error_fragment!r}, got {parsed_query.errors!r}"
        )
        return False

    if (
        case.expected_warning_fragment is not None
        and case.expected_warning_fragment not in "；".join(parsed_query.warnings)
    ):
        print(
            "failed: expected warnings to contain "
            f"{case.expected_warning_fragment!r}, got {parsed_query.warnings!r}"
        )
        return False

    return True


def main() -> int:
    """Run logistics parser checks."""

    parser = LogisticsParameterParser()
    cases = build_cases()

    results = [
        run_case(
            parser=parser,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("logistics parameter parser check failed")
        return 1

    print("logistics parameter parser check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())