"""Boundary tests for local controlled price API.

Requirement:
The FastAPI server must already be running, for example:

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class PriceApiBoundaryCase:
    """One price API boundary test case."""

    name: str
    body: dict[str, object]
    expected_http_status: int
    expected_parse_status: str | None = None
    expected_handler_status: str | None = None
    expected_is_price_intent: bool | None = None
    expected_handoff_required: bool | None = None
    expected_answer_fragment: str | None = None


def build_cases() -> list[PriceApiBoundaryCase]:
    """Return deterministic API boundary test cases."""

    long_text = "价" * 501

    return [
        PriceApiBoundaryCase(
            name="empty text is rejected by request schema",
            body={
                "text": "",
            },
            expected_http_status=422,
        ),
        PriceApiBoundaryCase(
            name="blank text is handled as not price intent",
            body={
                "text": "   ",
            },
            expected_http_status=200,
            expected_parse_status="not_price_intent",
            expected_handler_status="invalid_request",
            expected_is_price_intent=False,
            expected_handoff_required=False,
            expected_answer_fragment="当前未识别为价格问题",
        ),
        PriceApiBoundaryCase(
            name="missing text is rejected by request schema",
            body={},
            expected_http_status=422,
        ),
        PriceApiBoundaryCase(
            name="text longer than max length is rejected",
            body={
                "text": long_text,
            },
            expected_http_status=422,
        ),
        PriceApiBoundaryCase(
            name="missing product reference requires handoff",
            body={
                "text": "多少钱",
            },
            expected_http_status=200,
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="请先提供 SKU、OEM 对照号或螺纹规格",
        ),
        PriceApiBoundaryCase(
            name="discount without product reference requires handoff",
            body={
                "text": "有没有优惠",
            },
            expected_http_status=200,
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="当前系统尚未接入正式价格表",
        ),
        PriceApiBoundaryCase(
            name="lowest price without product reference requires handoff",
            body={
                "text": "最低能便宜到多少",
            },
            expected_http_status=200,
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="当前系统尚未接入正式价格表",
        ),
        PriceApiBoundaryCase(
            name="shipping fee without product reference requires handoff",
            body={
                "text": "包邮吗",
            },
            expected_http_status=200,
            expected_parse_status="missing_product_reference",
            expected_handler_status="handoff",
            expected_is_price_intent=True,
            expected_handoff_required=True,
            expected_answer_fragment="物流费用或免运条件",
        ),
        PriceApiBoundaryCase(
            name="multiple SKU IDs are ambiguous",
            body={
                "text": "SKU001 和 SKU003 分别多少钱",
            },
            expected_http_status=200,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_is_price_intent=True,
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个 SKU",
        ),
        PriceApiBoundaryCase(
            name="multiple OEM reference numbers are ambiguous",
            body={
                "text": "43330-39585 和 12345-67890 多少钱",
            },
            expected_http_status=200,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_is_price_intent=True,
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个 OEM 对照号",
        ),
        PriceApiBoundaryCase(
            name="multiple thread specs are ambiguous",
            body={
                "text": "M8x1.25 和 M10x1.5 多少钱",
            },
            expected_http_status=200,
            expected_parse_status="ambiguous",
            expected_handler_status="invalid_request",
            expected_is_price_intent=True,
            expected_handoff_required=False,
            expected_answer_fragment="识别到多个螺纹规格",
        ),
        PriceApiBoundaryCase(
            name="non price intent is not handled as quote",
            body={
                "text": "SKU001 什么规格",
            },
            expected_http_status=200,
            expected_parse_status="not_price_intent",
            expected_handler_status="invalid_request",
            expected_is_price_intent=False,
            expected_handoff_required=False,
            expected_answer_fragment="当前未识别为价格问题",
        ),
    ]


def require_dict(value: Any) -> dict[str, Any]:
    """Require a dictionary response payload."""

    if not isinstance(value, dict):
        raise TypeError(f"response payload must be dict, got {type(value).__name__}")

    return value


def require_string(
    payload: dict[str, Any],
    key: str,
) -> str:
    """Read a required string field from response payload."""

    value = payload.get(key)

    if not isinstance(value, str):
        raise TypeError(f"{key} must be string, got {type(value).__name__}")

    return value


def assert_no_forbidden_price_content(answer_text: str) -> bool:
    """Check answer text contains no generated price or commitment."""

    forbidden_fragments = [
        "¥",
        "￥",
        "元",
        "折扣",
        "包邮",
        "免费发",
        "立减",
        "优惠价",
        "活动价",
        "最低价",
    ]

    for fragment in forbidden_fragments:
        if fragment in answer_text:
            print(
                "failed: answer_text must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    if "æ" in answer_text or "Ã" in answer_text:
        print("failed: response appears to contain mojibake")
        return False

    return True


def run_case(
    *,
    client: httpx.Client,
    base_url: str,
    case: PriceApiBoundaryCase,
) -> bool:
    """Run one price API boundary case."""

    url = f"{base_url.rstrip('/')}/api/v1/price/query"

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"body: {case.body}")

    try:
        response = client.post(
            url,
            json=case.body,
        )
    except httpx.RequestError as exc:
        print(f"request failed: {exc}")
        return False

    print(f"http_status: {response.status_code}")

    if response.status_code != case.expected_http_status:
        print(
            "failed: expected http status "
            f"{case.expected_http_status}, got {response.status_code}"
        )
        print(response.text)
        return False

    payload = require_dict(response.json())

    if response.status_code == 422:
        detail = payload.get("detail")
        print("validation detail:")
        print(detail)

        if detail is None:
            print("failed: 422 response must include detail")
            return False

        return True

    print(f"parse_status: {payload.get('parse_status')}")
    print(f"is_price_intent: {payload.get('is_price_intent')}")
    print(f"price_query_type: {payload.get('price_query_type')}")
    print(f"product_reference_type: {payload.get('product_reference_type')}")
    print(f"product_reference_value: {payload.get('product_reference_value')}")
    print(f"quantity: {payload.get('quantity')}")
    print(f"handler_status: {payload.get('handler_status')}")
    print(f"handoff_required: {payload.get('handoff_required')}")

    answer_text = require_string(payload, "answer_text")

    print("answer_text:")
    print(answer_text)

    expected_pairs = [
        ("parse_status", case.expected_parse_status),
        ("handler_status", case.expected_handler_status),
        ("is_price_intent", case.expected_is_price_intent),
        ("handoff_required", case.expected_handoff_required),
    ]

    for key, expected_value in expected_pairs:
        if payload.get(key) != expected_value:
            print(
                f"failed: expected {key} {expected_value!r}, "
                f"got {payload.get(key)!r}"
            )
            return False

    if (
        case.expected_answer_fragment is not None
        and case.expected_answer_fragment not in answer_text
    ):
        print(
            "failed: expected answer_text to contain "
            f"{case.expected_answer_fragment!r}"
        )
        return False

    return assert_no_forbidden_price_content(answer_text)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Boundary test local controlled price API.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="FastAPI base URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds.",
    )

    return parser.parse_args()


def main() -> int:
    """Run price API boundary tests."""

    args = parse_args()
    cases = build_cases()

    with httpx.Client(timeout=args.timeout) as client:
        results = [
            run_case(
                client=client,
                base_url=args.base_url,
                case=case,
            )
            for case in cases
        ]

    print("=" * 80)

    if not all(results):
        print("price API boundary test failed")
        return 1

    print("price API boundary test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())