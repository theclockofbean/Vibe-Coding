# ruff: noqa: E402,I001
"""Check Phase 1 API routes.

This script verifies that Phase 1 API routes are mounted and can return stable
controlled responses through FastAPI TestClient.

Covered routes:
- POST /api/v1/spec/query
- POST /api/v1/price/query
- POST /api/v1/logistics/query
- POST /api/v1/quality/query
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

from app.main import app


REQUIRED_ROUTES: Final[set[str]] = {
    "/api/v1/spec/query",
    "/api/v1/price/query",
    "/api/v1/logistics/query",
    "/api/v1/quality/query",
}

COMMON_RESPONSE_KEYS: Final[tuple[str, ...]] = (
    "parse_status",
    "answer_text",
    "handoff_required",
    "source_references",
)


@dataclass(frozen=True)
class Phase1APIRouteCase:
    """One Phase 1 API route check case."""

    name: str
    endpoint: str
    text: str
    expected_parse_status: str
    expected_handoff_required: bool
    expected_answer_fragments: tuple[str, ...] = ()
    expected_fields: tuple[tuple[str, object | None], ...] = ()
    forbidden_answer_fragments: tuple[str, ...] = ()


def build_cases() -> list[Phase1APIRouteCase]:
    """Return deterministic Phase 1 route check cases."""

    return [
        Phase1APIRouteCase(
            name="spec_success",
            endpoint="/api/v1/spec/query",
            text="SKU001 螺纹是多少",
            expected_parse_status="parsed",
            expected_handoff_required=False,
            expected_fields=(
                ("query_type", "sku_id"),
                ("query_value", "SKU001"),
            ),
            expected_answer_fragments=(
                "SKU001",
                "螺纹规格",
            ),
        ),
        Phase1APIRouteCase(
            name="price_controlled_handoff",
            endpoint="/api/v1/price/query",
            text="SKU001 多少钱",
            expected_parse_status="parsed",
            expected_handoff_required=True,
            expected_fields=(
                ("is_price_intent", True),
                ("handler_status", "handoff"),
                ("price_query_type", "general_price"),
                ("product_reference_value", "SKU001"),
            ),
            expected_answer_fragments=(
                "SKU001",
                "不能直接给出报价",
                "转人工确认",
            ),
        ),
        Phase1APIRouteCase(
            name="logistics_success",
            endpoint="/api/v1/logistics/query",
            text="SKU001 几天发货",
            expected_parse_status="parsed",
            expected_handoff_required=False,
            expected_fields=(
                ("is_logistics_intent", True),
                ("handler_status", "success"),
                ("logistics_query_type", "shipping_time"),
            ),
            expected_answer_fragments=(
                "SKU001",
                "发货周期",
                "不代表到货时间",
            ),
            forbidden_answer_fragments=(
                "保证到",
                "可以包邮",
                "免运费",
                "今天一定发",
            ),
        ),
        Phase1APIRouteCase(
            name="quality_success",
            endpoint="/api/v1/quality/query",
            text="SKU001 什么材质",
            expected_parse_status="parsed",
            expected_handoff_required=False,
            expected_fields=(
                ("is_quality_intent", True),
                ("handler_status", "success"),
                ("quality_query_type", "material"),
            ),
            expected_answer_fragments=(
                "SKU001",
                "登记材质",
                "不代表额外质量承诺",
            ),
            forbidden_answer_fragments=(
                "保证不会坏",
                "保证不生锈",
                "保证不掉漆",
                "一年质保",
                "一定能退",
                "一定赔",
            ),
        ),
        Phase1APIRouteCase(
            name="quality_rejects_logistics_intent",
            endpoint="/api/v1/quality/query",
            text="SKU001 几天发货",
            expected_parse_status="not_quality_intent",
            expected_handoff_required=False,
            expected_fields=(
                ("is_quality_intent", False),
                ("handler_status", "invalid_request"),
            ),
            expected_answer_fragments=("当前未识别为质量问题",),
        ),
        Phase1APIRouteCase(
            name="logistics_rejects_quality_intent",
            endpoint="/api/v1/logistics/query",
            text="SKU001 什么材质",
            expected_parse_status="not_logistics_intent",
            expected_handoff_required=False,
            expected_fields=(
                ("is_logistics_intent", False),
                ("handler_status", "invalid_request"),
            ),
            expected_answer_fragments=("当前未识别为物流问题",),
        ),
    ]


def get_registered_route_paths() -> set[str]:
    """Return registered FastAPI route paths."""

    route_paths: set[str] = set()

    for route in app.routes:
        path = getattr(route, "path", None)

        if isinstance(path, str):
            route_paths.add(path)

    return route_paths


def check_required_routes() -> bool:
    """Check all required Phase 1 routes are registered."""

    print("=" * 80)
    print("checking required route registration")

    route_paths = get_registered_route_paths()
    missing_routes = REQUIRED_ROUTES - route_paths

    print("registered phase1-like routes:")
    pprint(sorted(path for path in route_paths if path.startswith("/api/v1/")))

    if missing_routes:
        print("failed: missing routes:")
        pprint(sorted(missing_routes))
        return False

    print("all required routes are registered")
    return True


def assert_common_response_shape(payload: dict[str, Any]) -> bool:
    """Check common response keys exist."""

    for key in COMMON_RESPONSE_KEYS:
        if key not in payload:
            print(f"failed: response missing common key {key!r}")
            return False

    if not isinstance(payload["answer_text"], str) or not payload["answer_text"]:
        print("failed: answer_text must be a non-empty string")
        return False

    if not isinstance(payload["source_references"], list):
        print("failed: source_references must be a list")
        return False

    return True


def run_route_case(
    *,
    client: TestClient,
    case: Phase1APIRouteCase,
) -> bool:
    """Run one route smoke case."""

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"endpoint: {case.endpoint}")
    print(f"text: {case.text}")

    response = client.post(
        case.endpoint,
        json={
            "text": case.text,
            "limit": 5,
        },
    )

    if response.status_code != 200:
        print(f"failed: expected HTTP 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_common_response_shape(payload):
        return False

    checks: list[tuple[str, object | None, object | None]] = [
        ("parse_status", case.expected_parse_status, payload["parse_status"]),
        (
            "handoff_required",
            case.expected_handoff_required,
            payload["handoff_required"],
        ),
    ]

    for field_name, expected_value in case.expected_fields:
        checks.append((field_name, expected_value, payload.get(field_name)))

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
                "failed: answer_text must not contain forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def main() -> int:
    """Run Phase 1 API route checks."""

    client = TestClient(app)

    route_result = check_required_routes()

    case_results = [
        run_route_case(
            client=client,
            case=case,
        )
        for case in build_cases()
    ]

    print("=" * 80)

    if not all([route_result, *case_results]):
        print("phase1 API route check failed")
        return 1

    print("phase1 API route check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())