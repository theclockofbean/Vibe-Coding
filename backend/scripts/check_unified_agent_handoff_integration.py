# ruff: noqa: E402,I001
"""Check Unified Agent API handoff ticket integration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from fastapi.testclient import TestClient
from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory
from app.main import app


AGENT_ENDPOINT: Final[str] = "/api/v1/agent/query"
HANDOFF_ENDPOINT: Final[str] = "/api/v1/handoff/tickets"
TEST_SOURCE_CHANNEL: Final[str] = "handoff_integration_test"


@dataclass(frozen=True)
class HandoffIntegrationCase:
    """One unified agent handoff integration case."""

    name: str
    text: str
    expected_selected_module: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_ticket_created: bool
    expected_answer_fragments: tuple[str, ...]


def cleanup_test_tickets() -> None:
    """Delete integration test tickets."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM handoff_tickets
                    WHERE source_channel = :source_channel;
                    """
                ),
                {
                    "source_channel": TEST_SOURCE_CHANNEL,
                },
            )


def build_cases() -> list[HandoffIntegrationCase]:
    """Return deterministic integration cases."""

    return [
        HandoffIntegrationCase(
            name="price_creates_ticket",
            text="SKU001 多少钱",
            expected_selected_module="price",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=(
                "SKU001",
                "不能直接给出报价",
            ),
        ),
        HandoffIntegrationCase(
            name="quality_creates_ticket",
            text="SKU001 会不会生锈",
            expected_selected_module="quality",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=(
                "SKU001",
                "不能自动承诺不生锈",
            ),
        ),
        HandoffIntegrationCase(
            name="logistics_fee_creates_ticket",
            text="SKU001 运费多少",
            expected_selected_module="logistics",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=(
                "转人工",
            ),
        ),
        HandoffIntegrationCase(
            name="spec_does_not_create_ticket",
            text="SKU001 螺纹是多少",
            expected_selected_module="spec",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_ticket_created=False,
            expected_answer_fragments=(
                "SKU001",
                "螺纹规格",
            ),
        ),
    ]


def assert_agent_response_shape(payload: dict[str, Any]) -> bool:
    """Check required unified agent response keys."""

    required_keys = {
        "selected_module",
        "route_status",
        "parse_status",
        "handler_status",
        "answer_text",
        "handoff_required",
        "handoff_ticket_id",
        "handoff_ticket_no",
        "warnings",
    }

    missing = required_keys - set(payload)

    if missing:
        print("failed: missing response keys")
        pprint(sorted(missing))
        return False

    return True


def assert_no_forbidden_fragments(answer_text: str) -> bool:
    """Check answer text contains no unsupported commitments."""

    forbidden_fragments = [
        "保证最低价",
        "一定包邮",
        "保证到货",
        "今天一定发",
        "保证不坏",
        "保证不生锈",
        "保证不掉漆",
        "一年质保",
        "终身质保",
        "七天无理由",
        "一定能退",
        "一定能换",
        "一定赔",
        "一定补发",
        "质量很好",
        "放心用",
        "完全没问题",
    ]

    for fragment in forbidden_fragments:
        if fragment in answer_text:
            print(
                "failed: answer_text contains forbidden fragment "
                f"{fragment!r}"
            )
            return False

    return True


def assert_ticket_visible_through_api(
    *,
    client: TestClient,
    ticket_no: str,
    selected_module: str,
) -> bool:
    """Check created ticket can be queried through handoff API."""

    response = client.get(
        HANDOFF_ENDPOINT,
        params={
            "selected_module": selected_module,
            "limit": 100,
            "offset": 0,
        },
    )

    if response.status_code != 200:
        print(f"failed: handoff API expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    items = payload.get("items")

    if not isinstance(items, list):
        print("failed: handoff API items must be list")
        return False

    matching_items = [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("ticket_no") == ticket_no
    ]

    if not matching_items:
        print(f"failed: ticket {ticket_no!r} not found through handoff API")
        return False

    ticket = matching_items[0]

    checks = [
        ticket.get("selected_module") == selected_module,
        ticket.get("status") == "open",
        ticket.get("source_channel") == TEST_SOURCE_CHANNEL,
        isinstance(ticket.get("handoff_reason"), str),
        bool(ticket.get("handoff_reason")),
    ]

    if not all(checks):
        print("failed: queried ticket content mismatch")
        pprint(ticket)
        return False

    return True


def run_case(
    *,
    client: TestClient,
    case: HandoffIntegrationCase,
) -> bool:
    """Run one handoff integration case."""

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"text: {case.text}")

    response = client.post(
        AGENT_ENDPOINT,
        json={
            "text": case.text,
            "limit": 5,
            "source_channel": TEST_SOURCE_CHANNEL,
            "session_id": "session-handoff-integration-test",
            "user_id": "user-handoff-integration-test",
        },
    )

    if response.status_code != 200:
        print(f"failed: expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_agent_response_shape(payload):
        return False

    checks: list[tuple[str, object | None, object | None]] = [
        (
            "selected_module",
            case.expected_selected_module,
            payload["selected_module"],
        ),
        (
            "handler_status",
            case.expected_handler_status,
            payload["handler_status"],
        ),
        (
            "handoff_required",
            case.expected_handoff_required,
            payload["handoff_required"],
        ),
    ]

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

    if not assert_no_forbidden_fragments(answer_text):
        return False

    ticket_id = payload.get("handoff_ticket_id")
    ticket_no = payload.get("handoff_ticket_no")

    if case.expected_ticket_created:
        if not isinstance(ticket_id, int):
            print("failed: handoff_ticket_id must be int")
            return False

        if not isinstance(ticket_no, str) or not ticket_no.startswith("HT-"):
            print("failed: handoff_ticket_no must start with HT-")
            return False

        return assert_ticket_visible_through_api(
            client=client,
            ticket_no=ticket_no,
            selected_module=case.expected_selected_module,
        )

    if ticket_id is not None or ticket_no is not None:
        print("failed: non-handoff case must not create ticket")
        return False

    return True


def main() -> int:
    """Run unified agent handoff integration checks."""

    cleanup_test_tickets()

    try:
        client = TestClient(app)
        results = [
            run_case(
                client=client,
                case=case,
            )
            for case in build_cases()
        ]
    finally:
        cleanup_test_tickets()

    print("=" * 80)

    if not all(results):
        print("unified agent handoff integration check failed")
        return 1

    print("unified agent handoff integration check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())