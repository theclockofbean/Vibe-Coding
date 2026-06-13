"""Check PriceHandler.

This script verifies price handler behavior.
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

from app.agent.handlers import PriceHandler  # noqa: E402
from app.agent.parsers import PriceParameterParser  # noqa: E402


@dataclass(frozen=True)
class PriceHandlerCheckCase:
    """One price handler check case."""

    text: str
    expected_parse_status: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_matched_count: int
    expected_reference_value: str | None


def build_cases() -> list[PriceHandlerCheckCase]:
    """Return deterministic handler check cases."""

    return [
        PriceHandlerCheckCase(
            text="SKU001 多少钱",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_reference_value="SKU001",
        ),
        PriceHandlerCheckCase(
            text="sku1 单价多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_reference_value="SKU001",
        ),
        PriceHandlerCheckCase(
            text="SKU001 100个多少钱",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_reference_value="SKU001",
        ),
        PriceHandlerCheckCase(
            text="43330-39585 报价",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_reference_value="43330-39585",
        ),
        PriceHandlerCheckCase(
            text="M10*1.5 批发价多少",
            expected_parse_status="parsed",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=1,
            expected_reference_value="M10×1.5",
        ),
        PriceHandlerCheckCase(
            text="多少钱",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=0,
            expected_reference_value=None,
        ),
        PriceHandlerCheckCase(
            text="有没有优惠",
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_matched_count=0,
            expected_reference_value=None,
        ),
        PriceHandlerCheckCase(
            text="43330-39585 和 12345-67890 多少钱",
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_matched_count=0,
            expected_reference_value=None,
        ),
        PriceHandlerCheckCase(
            text="SKU001 什么规格",
            expected_parse_status="not_price_intent",
            expected_handler_status="invalid_request",
            expected_handoff_required=False,
            expected_matched_count=0,
            expected_reference_value=None,
        ),
    ]


def run_case(
    *,
    parser: PriceParameterParser,
    handler: PriceHandler,
    case: PriceHandlerCheckCase,
) -> bool:
    """Run one handler check case."""

    print("=" * 80)
    print(f"text: {case.text}")

    parsed_query = parser.parse(case.text)
    handler_result = handler.handle(parsed_query)

    pprint(handler_result.to_dict())

    if parsed_query.status != case.expected_parse_status:
        print(
            "failed: expected parse status "
            f"{case.expected_parse_status!r}, got {parsed_query.status!r}"
        )
        return False

    if handler_result.status != case.expected_handler_status:
        print(
            "failed: expected handler status "
            f"{case.expected_handler_status!r}, got {handler_result.status!r}"
        )
        return False

    if handler_result.handoff_required != case.expected_handoff_required:
        print(
            "failed: expected handoff_required "
            f"{case.expected_handoff_required!r}, "
            f"got {handler_result.handoff_required!r}"
        )
        return False

    if handler_result.matched_count != case.expected_matched_count:
        print(
            "failed: expected matched_count "
            f"{case.expected_matched_count}, got {handler_result.matched_count}"
        )
        return False

    if handler_result.facts is None:
        print("failed: handler facts must not be None")
        return False

    if (
        handler_result.facts.get("product_reference_value")
        != case.expected_reference_value
    ):
        print(
            "failed: product_reference_value mismatch, expected "
            f"{case.expected_reference_value!r}, got "
            f"{handler_result.facts.get('product_reference_value')!r}"
        )
        return False

    if handler_result.facts.get("pricing_available") is not False:
        print("failed: pricing_available must be False")
        return False

    if handler_result.facts.get("requires_human_quote") is not True:
        print("failed: requires_human_quote must be True")
        return False

    fact_text = str(handler_result.facts)

    forbidden_fragments = [
        "¥",
        "￥",
        "元",
        "折",
        "包邮",
    ]

    for forbidden_fragment in forbidden_fragments:
        if forbidden_fragment in fact_text:
            print(
                "failed: handler facts must not contain forbidden fragment "
                f"{forbidden_fragment!r}"
            )
            return False

    return True


def main() -> int:
    """Run price handler checks."""

    parser = PriceParameterParser()
    handler = PriceHandler()
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
        print("price handler check failed")
        return 1

    print("price handler check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())