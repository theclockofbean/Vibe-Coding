# ruff: noqa: E402,I001
"""Check handoff ticket API."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory
from app.main import app
from app.repositories.handoff_ticket_repository import (
    HandoffTicketCreate,
    HandoffTicketRepository,
)


ENDPOINT: Final[str] = "/api/v1/handoff/tickets"
TEST_TICKET_PREFIX: Final[str] = "HT-API-"
TEST_SOURCE_CHANNEL: Final[str] = "api_test"


def cleanup_test_tickets() -> None:
    """Delete API test tickets."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM handoff_tickets
                    WHERE ticket_no LIKE :ticket_no_prefix
                       OR source_channel = :source_channel;
                    """
                ),
                {
                    "ticket_no_prefix": f"{TEST_TICKET_PREFIX}%",
                    "source_channel": TEST_SOURCE_CHANNEL,
                },
            )


def make_ticket_no() -> str:
    """Create unique test ticket number."""

    return f"{TEST_TICKET_PREFIX}{uuid4().hex[:12].upper()}"


def seed_test_tickets() -> list[str]:
    """Seed deterministic API test tickets."""

    session_factory = get_session_factory()
    created_ticket_numbers: list[str] = []

    with session_factory() as session:
        repository = HandoffTicketRepository(session)

        with session.begin():
            price_ticket = repository.create(
                HandoffTicketCreate(
                    ticket_no=make_ticket_no(),
                    user_text="SKU001 多少钱",
                    source_channel=TEST_SOURCE_CHANNEL,
                    selected_module="price",
                    route_status="routed",
                    route_confidence=0.75,
                    candidate_modules=["price"],
                    matched_signals=["多少钱"],
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_reason=(
                        "当前系统未接入正式价格表，不能自动报价，需人工确认。"
                    ),
                    answer_text="价格问题需转人工确认。",
                    module_payload={
                        "selected_module": "price",
                        "handler_status": "handoff",
                    },
                    risk_reasons=["price_without_price_table"],
                )
            )

            quality_ticket = repository.create(
                HandoffTicketCreate(
                    ticket_no=make_ticket_no(),
                    user_text="SKU001 会不会生锈",
                    source_channel=TEST_SOURCE_CHANNEL,
                    selected_module="quality",
                    route_status="routed",
                    route_confidence=0.75,
                    candidate_modules=["quality"],
                    matched_signals=["生锈"],
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_reason=(
                        "该质量问题涉及质量表现、售后责任、质保、退换或赔付，"
                        "需人工确认。"
                    ),
                    answer_text="质量承诺问题需转人工确认。",
                    source_references=[
                        {
                            "source_type": "database_table",
                            "source_name": "products",
                            "reference_id": "SKU001",
                        }
                    ],
                    module_payload={
                        "selected_module": "quality",
                        "handler_status": "handoff",
                    },
                    risk_reasons=["quality_commitment_required"],
                )
            )

            resolved_ticket = repository.create(
                HandoffTicketCreate(
                    ticket_no=make_ticket_no(),
                    user_text="SKU001 运费多少",
                    source_channel=TEST_SOURCE_CHANNEL,
                    status="resolved",
                    selected_module="logistics",
                    route_status="routed",
                    route_confidence=0.75,
                    candidate_modules=["logistics"],
                    matched_signals=["运费"],
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_reason=(
                        "该物流问题涉及运费、包邮、到货时间、承运商或加急承诺，"
                        "需人工确认。"
                    ),
                    answer_text="物流费用问题需转人工确认。",
                    module_payload={
                        "selected_module": "logistics",
                        "handler_status": "handoff",
                    },
                    risk_reasons=["logistics_commitment_required"],
                )
            )

            created_ticket_numbers.extend(
                [
                    price_ticket.ticket_no,
                    quality_ticket.ticket_no,
                    resolved_ticket.ticket_no,
                ]
            )

    return created_ticket_numbers


def get_registered_route_paths() -> set[str]:
    """Return registered FastAPI route paths."""

    paths: set[str] = set()

    for route in app.routes:
        path = getattr(route, "path", None)

        if isinstance(path, str):
            paths.add(path)

    return paths


def check_route_registered() -> bool:
    """Check handoff ticket route is registered."""

    print("=" * 80)
    print("checking handoff ticket API route")

    paths = get_registered_route_paths()

    if ENDPOINT not in paths:
        print(f"failed: missing route {ENDPOINT}")
        pprint(sorted(path for path in paths if path.startswith("/api/v1/")))
        return False

    print(f"route registered: {ENDPOINT}")
    return True


def assert_response_shape(payload: dict[str, Any]) -> bool:
    """Check list response shape."""

    required_keys = {
        "items",
        "total",
        "limit",
        "offset",
        "filters",
    }

    missing = required_keys - set(payload)

    if missing:
        print("failed: missing response keys")
        pprint(sorted(missing))
        return False

    if not isinstance(payload["items"], list):
        print("failed: items must be a list")
        return False

    if not isinstance(payload["total"], int):
        print("failed: total must be an int")
        return False

    if not isinstance(payload["filters"], dict):
        print("failed: filters must be a dict")
        return False

    return True


def check_list_default(
    *,
    client: TestClient,
    expected_ticket_numbers: list[str],
) -> bool:
    """Check default ticket list."""

    print("=" * 80)
    print("checking default list")

    response = client.get(ENDPOINT)

    if response.status_code != 200:
        print(f"failed: expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_response_shape(payload):
        return False

    returned_ticket_numbers = {
        str(item["ticket_no"])
        for item in payload["items"]
        if isinstance(item, dict) and "ticket_no" in item
    }

    if not set(expected_ticket_numbers).issubset(returned_ticket_numbers):
        print("failed: seeded tickets not found in default list")
        print("expected:")
        pprint(expected_ticket_numbers)
        print("returned:")
        pprint(sorted(returned_ticket_numbers))
        return False

    return True


def check_status_filter(
    *,
    client: TestClient,
) -> bool:
    """Check status filter."""

    print("=" * 80)
    print("checking status filter")

    response = client.get(
        ENDPOINT,
        params={
            "status": "resolved",
            "limit": 20,
            "offset": 0,
        },
    )

    if response.status_code != 200:
        print(f"failed: expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_response_shape(payload):
        return False

    if payload["filters"]["status"] != "resolved":
        print("failed: status filter echo mismatch")
        return False

    matching_test_items = [
        item
        for item in payload["items"]
        if isinstance(item, dict)
        and str(item.get("ticket_no", "")).startswith(TEST_TICKET_PREFIX)
    ]

    if not matching_test_items:
        print("failed: expected at least one resolved test ticket")
        return False

    return all(item.get("status") == "resolved" for item in matching_test_items)


def check_selected_module_filter(
    *,
    client: TestClient,
) -> bool:
    """Check selected_module filter."""

    print("=" * 80)
    print("checking selected_module filter")

    response = client.get(
        ENDPOINT,
        params={
            "selected_module": "quality",
            "limit": 20,
            "offset": 0,
        },
    )

    if response.status_code != 200:
        print(f"failed: expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_response_shape(payload):
        return False

    if payload["filters"]["selected_module"] != "quality":
        print("failed: selected_module filter echo mismatch")
        return False

    matching_test_items = [
        item
        for item in payload["items"]
        if isinstance(item, dict)
        and str(item.get("ticket_no", "")).startswith(TEST_TICKET_PREFIX)
    ]

    if not matching_test_items:
        print("failed: expected at least one quality test ticket")
        return False

    return all(
        item.get("selected_module") == "quality"
        for item in matching_test_items
    )


def check_pagination(
    *,
    client: TestClient,
) -> bool:
    """Check pagination parameters."""

    print("=" * 80)
    print("checking pagination")

    response = client.get(
        ENDPOINT,
        params={
            "limit": 1,
            "offset": 0,
        },
    )

    if response.status_code != 200:
        print(f"failed: expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_response_shape(payload):
        return False

    if payload["limit"] != 1:
        print("failed: expected limit echo to be 1")
        return False

    return len(payload["items"]) <= 1


def check_limit_boundaries(
    *,
    client: TestClient,
) -> bool:
    """Check limit and offset HTTP boundaries."""

    print("=" * 80)
    print("checking limit and offset boundaries")

    cases = [
        (
            {
                "limit": 0,
            },
            422,
        ),
        (
            {
                "limit": 101,
            },
            422,
        ),
        (
            {
                "offset": -1,
            },
            422,
        ),
    ]

    results: list[bool] = []

    for params, expected_status_code in cases:
        response = client.get(
            ENDPOINT,
            params=params,
        )
        print(f"params={params} status_code={response.status_code}")

        if response.status_code != expected_status_code:
            print(
                "failed: expected status "
                f"{expected_status_code}, got {response.status_code}"
            )
            print(response.text)
            results.append(False)
        else:
            results.append(True)

    return all(results)


def main() -> int:
    """Run handoff ticket API checks."""

    cleanup_test_tickets()
    ticket_numbers = seed_test_tickets()

    try:
        client = TestClient(app)

        results = [
            check_route_registered(),
            check_list_default(
                client=client,
                expected_ticket_numbers=ticket_numbers,
            ),
            check_status_filter(client=client),
            check_selected_module_filter(client=client),
            check_pagination(client=client),
            check_limit_boundaries(client=client),
        ]
    finally:
        cleanup_test_tickets()

    print("=" * 80)

    if not all(results):
        print("handoff ticket API check failed")
        return 1

    print("handoff ticket API check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())