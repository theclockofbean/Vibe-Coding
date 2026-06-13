"""Check LogisticsHandler.

This script verifies logistics handler behavior.

It reads products from the local database, but does not call an LLM,
calculate shipping fees, promise delivery time, promise free shipping,
or write data.
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

from app.agent.handlers import LogisticsHandler  # noqa: E402
from app.agent.parsers import LogisticsParameterParser  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402


@dataclass(frozen=True)
class LogisticsHandlerCheckCase:
    """One logistics handler check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_matched_count: int | None = None
    expected_query_type: str | None = None
    expected_fact_key: str | None = None
    expected_fact_value: object | None = None
    expected_error_fragment: str | None = None


def build_cases() -> list[LogisticsHandlerCheckCase]:
    """Return deterministic handler check cases."""

    return [
        LogisticsHandlerCheckCase(
            text="SKU001 几天发货",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_matched_count=1,
            expected_query_type="shipping_time",
            expected_fact_key="delivery_time_committed",
            expected_fact_value=False,
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 有现货吗",
            expected_parse_status="parsed",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_matched_count=1,
            expected_query_type="stock_status",
            expected_fact_key="stock_status_available",
            expected_fact_value=True,
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 运费多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_query_type="shipping_fee",
            expected_fact_key="shipping_fee_committed",
            expected_fact_value=False,
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 包邮吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_query_type="free_shipping",
            expected_fact_key="free_shipping_committed",
            expected_fact_value=False,
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 发到杭州几天",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_query_type="delivery_time",
            expected_fact_key="delivery_time_committed",
            expected_fact_value=False,
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 发什么快递",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_query_type="carrier",
            expected_fact_key="carrier_committed",
            expected_fact_value=False,
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 能加急吗",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_query_type="expedite",
            expected_fact_key="expedite_committed",
            expected_fact_value=False,
        ),
        LogisticsHandlerCheckCase(
            text="物流单号呢",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=0,
            expected_query_type="tracking",
            expected_fact_key="tracking_supported",
            expected_fact_value=False,
            expected_error_fragment="missing product reference",
        ),
        LogisticsHandlerCheckCase(
            text="几天发货",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=0,
            expected_query_type="shipping_time",
            expected_error_fragment="missing product reference",
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 和 SKU003 分别几天发货",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_matched_count=0,
            expected_query_type="shipping_time",
            expected_error_fragment="multiple SKU IDs found",
        ),
        LogisticsHandlerCheckCase(
            text="SKU001 多少钱",
            expected_parse_status="not_logistics_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_matched_count=0,
        ),
        LogisticsHandlerCheckCase(
            text="SKU999 几天发货",
            expected_parse_status="parsed",
            expected_handler_status="not_found",
            expected_handoff_required=True,
            expected_matched_count=0,
            expected_query_type="shipping_time",
            expected_error_fragment="product not found",
        ),
    ]


def require_facts(value: dict[str, object] | None) -> dict[str, object]:
    """Require non-empty facts dictionary."""

    if value is None:
        raise AssertionError("handler facts must not be None")

    return value


def require_products(facts: dict[str, object]) -> list[dict[str, object]]:
    """Read products from facts."""

    products = facts.get("products")

    if not isinstance(products, list):
        raise AssertionError("facts['products'] must be a list")

    result: list[dict[str, object]] = []

    for product in products:
        if not isinstance(product, dict):
            raise AssertionError("every product fact must be a dict")
        result.append(product)

    return result


def assert_no_forbidden_commitment_facts(facts: dict[str, object]) -> bool:
    """Check that handler facts do not contain unsupported commitment values."""

    expected_false_keys = [
        "delivery_time_committed",
        "shipping_fee_committed",
        "free_shipping_committed",
        "carrier_committed",
        "expedite_committed",
        "tracking_supported",
    ]

    for key in expected_false_keys:
        if facts.get(key) is not False:
            print(f"failed: facts[{key!r}] must be False")
            return False

    forbidden_fact_keys = [
        "shipping_fee_amount",
        "free_shipping_rule",
        "delivery_date",
        "carrier_name",
        "tracking_number",
        "expedite_available",
    ]

    for key in forbidden_fact_keys:
        if key in facts:
            print(f"failed: forbidden fact key exists: {key!r}")
            return False

    return True


def assert_matched_product_basics(
    *,
    facts: dict[str, object],
    expected_sku_id: str,
) -> bool:
    """Check matched product facts for known SKU."""

    products = require_products(facts)

    if not products:
        print("failed: expected at least one matched product")
        return False

    first_product = products[0]

    if first_product.get("sku_id") != expected_sku_id:
        print(
            "failed: expected first product sku_id "
            f"{expected_sku_id!r}, got {first_product.get('sku_id')!r}"
        )
        return False

    required_keys = [
        "product_name",
        "thread_spec",
        "oem_reference_number",
        "stock_status",
        "lead_time_days",
        "min_order_qty",
    ]

    for key in required_keys:
        if key not in first_product:
            print(f"failed: product fact missing key {key!r}")
            return False

    return True


def run_case(
    *,
    parser: LogisticsParameterParser,
    handler: LogisticsHandler,
    case: LogisticsHandlerCheckCase,
) -> bool:
    """Run one handler check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    handler_result = handler.handle(parsed_query)
    facts = require_facts(handler_result.facts)

    pprint(handler_result.to_dict())

    checks: list[tuple[str, object | None, object | None]] = [
        ("parse_status", case.expected_parse_status, parsed_query.status),
        ("handler_status", case.expected_handler_status, handler_result.status),
        (
            "handoff_required",
            case.expected_handoff_required,
            handler_result.handoff_required,
        ),
        (
            "logistics_query_type",
            case.expected_query_type,
            facts.get("logistics_query_type"),
        ),
    ]

    for name, expected_value, actual_value in checks:
        if expected_value != actual_value:
            print(
                f"failed: {name} expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
            return False

    if (
        case.expected_matched_count is not None
        and handler_result.matched_count != case.expected_matched_count
    ):
        print(
            "failed: matched_count expected "
            f"{case.expected_matched_count}, got {handler_result.matched_count}"
        )
        return False

    if (
        case.expected_fact_key is not None
        and facts.get(case.expected_fact_key) != case.expected_fact_value
    ):
        print(
            "failed: fact "
            f"{case.expected_fact_key!r} expected "
            f"{case.expected_fact_value!r}, got "
            f"{facts.get(case.expected_fact_key)!r}"
        )
        return False

    if (
        case.expected_error_fragment is not None
        and case.expected_error_fragment not in "；".join(handler_result.errors)
    ):
        print(
            "failed: expected errors to contain "
            f"{case.expected_error_fragment!r}, got {handler_result.errors!r}"
        )
        return False

    if not assert_no_forbidden_commitment_facts(facts):
        return False

    if handler_result.matched_count > 0 and not assert_matched_product_basics(
        facts=facts,
        expected_sku_id="SKU001",
    ):
        return False

    return True


def build_handler() -> LogisticsHandler:
    """Build LogisticsHandler with database-backed repository."""

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        return LogisticsHandler(product_repository=product_repository)


def main() -> int:
    """Run logistics handler checks."""

    parser = LogisticsParameterParser()
    handler = build_handler()
    cases = build_cases()

    results = [
        run_case(
            parser=parser,
            handler=handler,
            case=case,
        )
        for case in cases
    ]

    print("=" * 80)

    if not all(results):
        print("logistics handler check failed")
        return 1

    print("logistics handler check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())