"""Boundary tests for local specification API.

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
class ApiBoundaryCase:
    """One API boundary test case."""

    name: str
    body: dict[str, object]
    expected_http_status: int
    expected_parse_status: str | None = None
    expected_query_type: str | None = None
    expected_answer_fragment: str | None = None


def build_cases() -> list[ApiBoundaryCase]:
    """Return deterministic API boundary test cases."""

    long_text = "查" * 501

    return [
        ApiBoundaryCase(
            name="empty text is rejected by request schema",
            body={
                "text": "",
                "limit": 5,
            },
            expected_http_status=422,
        ),
        ApiBoundaryCase(
            name="blank text enters parser and returns not_supported",
            body={
                "text": "   ",
                "limit": 5,
            },
            expected_http_status=200,
            expected_parse_status="not_supported",
            expected_query_type=None,
            expected_answer_fragment="text must not be blank",
        ),
        ApiBoundaryCase(
            name="limit zero is rejected by request schema",
            body={
                "text": "SKU001",
                "limit": 0,
            },
            expected_http_status=422,
        ),
        ApiBoundaryCase(
            name="limit greater than max is rejected by request schema",
            body={
                "text": "SKU001",
                "limit": 21,
            },
            expected_http_status=422,
        ),
        ApiBoundaryCase(
            name="missing text is rejected by request schema",
            body={
                "limit": 5,
            },
            expected_http_status=422,
        ),
        ApiBoundaryCase(
            name="missing limit uses default",
            body={
                "text": "SKU001",
            },
            expected_http_status=200,
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_answer_fragment="查到 SKU001",
        ),
        ApiBoundaryCase(
            name="text longer than max length is rejected",
            body={
                "text": long_text,
                "limit": 5,
            },
            expected_http_status=422,
        ),
        ApiBoundaryCase(
            name="multiple thread specs are ambiguous",
            body={
                "text": "M8x1.25 和 M10x1.5 都有哪些",
                "limit": 5,
            },
            expected_http_status=200,
            expected_parse_status="ambiguous",
            expected_query_type=None,
            expected_answer_fragment="识别到多个螺纹规格",
        ),
        ApiBoundaryCase(
            name="multiple OEM reference numbers are ambiguous",
            body={
                "text": "帮我查 43330-39585 和 12345-67890",
                "limit": 5,
            },
            expected_http_status=200,
            expected_parse_status="ambiguous",
            expected_query_type=None,
            expected_answer_fragment="识别到多个 OEM 对照号",
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


def run_case(
    *,
    client: httpx.Client,
    base_url: str,
    case: ApiBoundaryCase,
) -> bool:
    """Run one boundary case."""

    url = f"{base_url.rstrip('/')}/api/v1/spec/query"

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
    print(f"query_type: {payload.get('query_type')}")
    print(f"query_value: {payload.get('query_value')}")

    answer_text = require_string(payload, "answer_text")

    print("answer_text:")
    print(answer_text)

    if payload.get("parse_status") != case.expected_parse_status:
        print(
            "failed: expected parse_status "
            f"{case.expected_parse_status!r}, got {payload.get('parse_status')!r}"
        )
        return False

    if payload.get("query_type") != case.expected_query_type:
        print(
            "failed: expected query_type "
            f"{case.expected_query_type!r}, got {payload.get('query_type')!r}"
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

    if "价格" in answer_text:
        print("failed: spec API answer must not mention price")
        return False

    if "æ" in answer_text or "Ã" in answer_text:
        print("failed: response appears to contain mojibake")
        return False

    return True


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Boundary test local specification API.",
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
    """Run API boundary tests."""

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
        print("spec API boundary test failed")
        return 1

    print("spec API boundary test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())