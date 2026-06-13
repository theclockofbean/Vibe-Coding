"""Check QualityParameterParser."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.parsers.quality_parameter_parser import (  # noqa: E402
    QualityParameterParser,
)


@dataclass(frozen=True)
class QualityParserCheckCase:
    """One quality parser check case."""

    text: str
    expected_status: str
    expected_is_quality_intent: bool
    expected_quality_query_type: str | None
    expected_product_reference_type: str | None = None
    expected_product_reference_value: str | None = None
    expected_sku_ids: list[str] | None = None
    expected_oem_reference_numbers: list[str] | None = None
    expected_thread_specs: list[str] | None = None
    expected_error_fragment: str | None = None


def build_cases() -> list[QualityParserCheckCase]:
    """Return deterministic quality parser check cases."""

    return [
        QualityParserCheckCase(
            text="SKU001 什么材质",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="material",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        QualityParserCheckCase(
            text="sku001 是铝合金吗",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="material",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        QualityParserCheckCase(
            text="SKU001 表面怎么处理",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="surface_treatment",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
            expected_sku_ids=["SKU001"],
        ),
        QualityParserCheckCase(
            text="SKU001 耐用吗",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="durability",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="SKU001 会不会生锈",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="rust_resistance",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="SKU001 会不会掉漆",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="scratch_resistance",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="SKU001 质保多久",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="warranty",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="SKU001 不合适能退吗",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="return_exchange",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="质量问题能赔吗",
            expected_status="missing_product_reference",
            expected_is_quality_intent=True,
            expected_quality_query_type="compensation",
            expected_error_fragment="missing product reference",
        ),
        QualityParserCheckCase(
            text="SKU001 收到有划痕",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="defect_issue",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="SKU001 质量怎么样",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="durability",
            expected_product_reference_type="sku_id",
            expected_product_reference_value="SKU001",
        ),
        QualityParserCheckCase(
            text="43330-39585 会不会生锈",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="rust_resistance",
            expected_product_reference_type="oem_reference_number",
            expected_product_reference_value="43330-39585",
            expected_oem_reference_numbers=["43330-39585"],
        ),
        QualityParserCheckCase(
            text="M8x1.25 会不会掉漆",
            expected_status="parsed",
            expected_is_quality_intent=True,
            expected_quality_query_type="scratch_resistance",
            expected_product_reference_type="thread_spec",
            expected_product_reference_value="M8×1.25",
            expected_thread_specs=["M8×1.25"],
        ),
        QualityParserCheckCase(
            text="SKU001 几天发货",
            expected_status="not_quality_intent",
            expected_is_quality_intent=False,
            expected_quality_query_type=None,
        ),
        QualityParserCheckCase(
            text="SKU001 和 SKU003 哪个质量更好",
            expected_status="ambiguous",
            expected_is_quality_intent=True,
            expected_quality_query_type="general_quality",
            expected_sku_ids=["SKU001", "SKU003"],
            expected_error_fragment="multiple SKU IDs found in quality query",
        ),
        QualityParserCheckCase(
            text="43330-39585 和 12345-67890 哪个更耐用",
            expected_status="ambiguous",
            expected_is_quality_intent=True,
            expected_quality_query_type="durability",
            expected_oem_reference_numbers=[
                "43330-39585",
                "12345-67890",
            ],
            expected_error_fragment=(
                "multiple OEM reference numbers found in quality query"
            ),
        ),
        QualityParserCheckCase(
            text="M8x1.25 和 M10x1.5 哪个不容易坏",
            expected_status="ambiguous",
            expected_is_quality_intent=True,
            expected_quality_query_type="durability",
            expected_thread_specs=["M8×1.25", "M10×1.5"],
            expected_error_fragment="multiple thread specs found in quality query",
        ),
    ]


def assert_list_if_expected(
    *,
    field_name: str,
    expected_value: list[str] | None,
    actual_value: list[str],
) -> bool:
    """Assert list field only when expected value is provided."""

    if expected_value is None:
        return True

    if actual_value != expected_value:
        print(
            f"failed: {field_name} expected {expected_value!r}, "
            f"got {actual_value!r}"
        )
        return False

    return True


def run_case(
    *,
    parser: QualityParameterParser,
    case: QualityParserCheckCase,
) -> bool:
    """Run one parser check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    pprint(parsed_query.to_dict())

    checks: list[tuple[str, object | None, object | None]] = [
        ("status", case.expected_status, parsed_query.status),
        (
            "is_quality_intent",
            case.expected_is_quality_intent,
            parsed_query.is_quality_intent,
        ),
        (
            "quality_query_type",
            case.expected_quality_query_type,
            parsed_query.quality_query_type,
        ),
        (
            "product_reference_type",
            case.expected_product_reference_type,
            parsed_query.product_reference_type,
        ),
        (
            "product_reference_value",
            case.expected_product_reference_value,
            parsed_query.product_reference_value,
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    list_checks = [
        (
            "sku_ids",
            case.expected_sku_ids,
            parsed_query.sku_ids,
        ),
        (
            "oem_reference_numbers",
            case.expected_oem_reference_numbers,
            parsed_query.oem_reference_numbers,
        ),
        (
            "thread_specs",
            case.expected_thread_specs,
            parsed_query.thread_specs,
        ),
    ]

    for field_name, expected_value, actual_value in list_checks:
        if not assert_list_if_expected(
            field_name=field_name,
            expected_value=expected_value,
            actual_value=actual_value,
        ):
            return False

    if case.expected_error_fragment is not None:
        error_text = "；".join(parsed_query.errors)

        if case.expected_error_fragment not in error_text:
            print(
                "failed: expected errors to contain "
                f"{case.expected_error_fragment!r}, got {parsed_query.errors!r}"
            )
            return False

    return True


def main() -> int:
    """Run quality parser checks."""

    parser = QualityParameterParser()
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
        print("quality parameter parser check failed")
        return 1

    print("quality parameter parser check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())