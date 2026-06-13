"""Smoke test for local specification API.

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
class ApiCheckCase:
    """One API smoke test case."""

    text: str
    limit: int
    expected_parse_status: str
    expected_query_type: str | None
    expected_answer_fragment: str


def build_cases() -> list[ApiCheckCase]:
    """Return deterministic API smoke test cases."""

    return [
        ApiCheckCase(
            text="帮我查一下 SKU001 的规格",
            limit=5,
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_answer_fragment="查到 SKU001",
        ),
        ApiCheckCase(
            text="M10*1.5 有哪些",
            limit=3,
            expected_parse_status="parsed",
            expected_query_type="thread_spec",
            expected_answer_fragment="共查到 3 个匹配产品",
        ),
        ApiCheckCase(
            text="OEM 43330-39585 对应哪个球头",
            limit=5,
            expected_parse_status="parsed",
            expected_query_type="oem_reference_number",
            expected_answer_fragment="SKU001",
        ),
        ApiCheckCase(
            text="SKU999 有吗",
            limit=5,
            expected_parse_status="parsed",
            expected_query_type="sku_id",
            expected_answer_fragment="没有在当前产品资料中查到",
        ),
        ApiCheckCase(
            text="帮我查 43330-39585 和 12345-67890",
            limit=5,
            expected_parse_status="ambiguous",
            expected_query_type=None,
            expected_answer_fragment="识别到多个 OEM 对照号",
        ),
        ApiCheckCase(
            text="你好，能介绍一下吗",
            limit=5,
            expected_parse_status="not_supported",
            expected_query_type=None,
            expected_answer_fragment="当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
        ),
    ]


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
    case: ApiCheckCase,
) -> bool:
    """Run one API check case."""

    url = f"{base_url.rstrip('/')}/api/v1/spec/query"

    print("=" * 80)
    print(f"text: {case.text}")

    try:
        response = client.post(
            url,
            json={
                "text": case.text,
                "limit": case.limit,
            },
        )
    except httpx.RequestError as exc:
        print(f"request failed: {exc}")
        return False

    print(f"http_status: {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        return False

    payload = response.json()

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

    if case.expected_answer_fragment not in answer_text:
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
        description="Smoke test local specification API.",
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
    """Run API smoke tests."""

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
        print("spec API smoke test failed")
        return 1

    print("spec API smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())