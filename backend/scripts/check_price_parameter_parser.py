"""Check PriceParameterParser.

This script validates deterministic price intent parsing.
It does not query the database and does not generate prices.
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

from app.agent.parsers import PriceParameterParser  # noqa: E402


@dataclass(frozen=True)
class PriceParserCheckCase:
    """One price parser check case."""

    text: str
    expected_status: str
    expected_is_price_intent: bool
    expected_price_query_type: str | None
    expected_product_reference_type: str | None
    expected_product_reference_value: str | None
    expected_quantity: int | None
    expected_error_fragment: str | None = None
    expected_warning_fragment: str | None = None


def build_cases() -> list[PriceParserCheckCase]:
    """Return deterministic parser check cases."""

    return [
        PriceParserCheckCase(
            text="SKU001 多少钱",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="sku1 单价多少",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="unit_price",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="SKU001 100个多少钱",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_quantity=100,
        ),
        PriceParserCheckCase(
            text="43330-39585 报价",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type="oem_reference_number",
            expected_product_reference_value="43330-39585",
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="M10*1.5 批发价多少",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="bulk_price",
            expected_product_reference_type="thread_spec",
            expected_product_reference_value="M10×1.5",
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="多少钱",
            expected_status="missing_product_reference",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
            expected_error_fragment="price intent found",
        ),
        PriceParserCheckCase(
            text="有没有优惠",
            expected_status="missing_product_reference",
            expected_is_price_intent=True,
            expected_price_query_type="discount",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="最低价多少",
            expected_status="missing_product_reference",
            expected_is_price_intent=True,
            expected_price_query_type="lowest_price",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="包邮吗",
            expected_status="missing_product_reference",
            expected_is_price_intent=True,
            expected_price_query_type="shipping_fee",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
        ),
        PriceParserCheckCase(
            text="43330-39585 和 12345-67890 多少钱",
            expected_status="ambiguous",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
            expected_error_fragment="multiple OEM reference numbers found",
        ),
        PriceParserCheckCase(
            text="M8x1.25 和 M10x1.5 多少钱",
            expected_status="ambiguous",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
            expected_error_fragment="multiple thread specs found",
        ),
        PriceParserCheckCase(
            text="SKU001 和 SKU003 分别多少钱",
            expected_status="ambiguous",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
            expected_error_fragment="multiple SKU IDs found in price query",
        ),
        PriceParserCheckCase(
            text="SKU001 和 43330-39585 多少钱",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_quantity=None,
            expected_warning_fragment="SKU ID has priority over OEM reference number",
        ),
        PriceParserCheckCase(
            text="43330-39585 和 M8x1.25 多少钱",
            expected_status="parsed",
            expected_is_price_intent=True,
            expected_price_query_type="general_price",
            expected_product_reference_type="oem_reference_number",
            expected_product_reference_value="43330-39585",
            expected_quantity=None,
            expected_warning_fragment="OEM reference number has priority over thread spec",
        ),
        PriceParserCheckCase(
            text="SKU001 什么规格",
            expected_status="not_price_intent",
            expected_is_price_intent=False,
            expected_price_query_type=None,
            expected_product_reference_type=None,
            expected_product_reference_value=None,
            expected_quantity=None,
        ),
    ]


def run_case(
    *,
    parser: PriceParameterParser,
    case: PriceParserCheckCase,
) -> bool:
    """Run one parser check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    payload = parsed_query.to_dict()

    pprint(payload)

    checks = [
        (
            parsed_query.status == case.expected_status,
            "status",
            case.expected_status,
            parsed_query.status,
        ),
        (
            parsed_query.is_price_intent == case.expected_is_price_intent,
            "is_price_intent",
            case.expected_is_price_intent,
            parsed_query.is_price_intent,
        ),
        (
            parsed_query.price_query_type == case.expected_price_query_type,
            "price_query_type",
            case.expected_price_query_type,
            parsed_query.price_query_type,
        ),
        (
            parsed_query.product_reference_type
            == case.expected_product_reference_type,
            "product_reference_type",
            case.expected_product_reference_type,
            parsed_query.product_reference_type,
        ),
        (
            parsed_query.product_reference_value
            == case.expected_product_reference_value,
            "product_reference_value",
            case.expected_product_reference_value,
            parsed_query.product_reference_value,
        ),
        (
            parsed_query.quantity == case.expected_quantity,
            "quantity",
            case.expected_quantity,
            parsed_query.quantity,
        ),
    ]

    for passed, field_name, expected, actual in checks:
        if not passed:
            print(
                f"failed: {field_name} expected {expected!r}, got {actual!r}"
            )
            return False

    if case.expected_error_fragment is not None:
        joined_errors = "；".join(parsed_query.errors)

        if case.expected_error_fragment not in joined_errors:
            print(
                "failed: expected errors to contain "
                f"{case.expected_error_fragment!r}"
            )
            return False

    if case.expected_warning_fragment is not None:
        joined_warnings = "；".join(parsed_query.warnings)

        if case.expected_warning_fragment not in joined_warnings:
            print(
                "failed: expected warnings to contain "
                f"{case.expected_warning_fragment!r}"
            )
            return False

    return True


def main() -> int:
    """Run price parser checks."""

    parser = PriceParameterParser()
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
        print("price parameter parser check failed")
        return 1

    print("price parameter parser check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())