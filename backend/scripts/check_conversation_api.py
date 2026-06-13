# ruff: noqa: E402,I001
"""Check Conversation API."""

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

from app.agent.services import ConversationService
from app.core.database import get_session_factory
from app.main import app
from app.repositories.conversation_repository import ConversationRepository


ENDPOINT: Final[str] = "/api/v1/agent/conversation"
TEST_SOURCE_CHANNEL: Final[str] = "conversation_api_test"


def cleanup_test_conversations() -> None:
    """Delete API test conversations."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM conversations
                    WHERE source_channel = :source_channel;
                    """
                ),
                {
                    "source_channel": TEST_SOURCE_CHANNEL,
                },
            )


def make_session_id() -> str:
    """Create unique test session ID."""

    return f"session-api-{uuid4().hex[:12]}"


def seed_conversation() -> str:
    """Seed one test conversation and return session_id."""

    session_id = make_session_id()
    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ConversationRepository(session)
        service = ConversationService(repository=repository)

        with session.begin():
            conversation = service.get_or_create_conversation(
                session_id=session_id,
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-api-test",
            )

            service.record_user_message(
                conversation=conversation,
                user_text="SKU001 多少钱",
            )

            service.record_agent_response(
                conversation=conversation,
                answer_text=(
                    "当前系统尚未接入正式价格表，不能直接给出报价。"
                    "请转人工确认。"
                ),
                agent_payload={
                    "selected_module": "price",
                    "route_status": "routed",
                    "parse_status": "parsed",
                    "handler_status": "handoff",
                    "handoff_required": True,
                    "handoff_ticket_id": 789,
                    "handoff_ticket_no": "HT-API-789",
                    "source_references": [],
                    "module_payload": {
                        "selected_module": "price",
                        "handler_status": "handoff",
                    },
                    "warnings": [],
                    "errors": [],
                },
            )

    return session_id


def get_registered_route_paths() -> set[str]:
    """Return registered FastAPI route paths."""

    paths: set[str] = set()

    for route in app.routes:
        path = getattr(route, "path", None)

        if isinstance(path, str):
            paths.add(path)

    return paths


def check_route_registered() -> bool:
    """Check conversation route is registered."""

    print("=" * 80)
    print("checking conversation API route")

    paths = get_registered_route_paths()

    if ENDPOINT not in paths:
        print(f"failed: missing route {ENDPOINT}")
        pprint(sorted(path for path in paths if path.startswith("/api/v1/")))
        return False

    print(f"route registered: {ENDPOINT}")
    return True


def assert_response_shape(payload: dict[str, Any]) -> bool:
    """Check response shape."""

    required_keys = {
        "session_id",
        "conversation",
        "items",
        "limit",
    }

    missing = required_keys - set(payload)

    if missing:
        print("failed: missing response keys")
        pprint(sorted(missing))
        return False

    if not isinstance(payload["items"], list):
        print("failed: items must be a list")
        return False

    if not isinstance(payload["limit"], int):
        print("failed: limit must be an int")
        return False

    return True


def check_existing_conversation(
    *,
    client: TestClient,
    session_id: str,
) -> bool:
    """Check querying an existing conversation."""

    print("=" * 80)
    print("checking existing conversation")

    response = client.get(
        ENDPOINT,
        params={
            "session_id": session_id,
            "limit": 20,
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

    if payload["session_id"] != session_id:
        print("failed: session_id echo mismatch")
        return False

    if not isinstance(payload["conversation"], dict):
        print("failed: conversation must be a dict")
        return False

    items = payload["items"]

    if len(items) != 2:
        print("failed: expected 2 messages")
        return False

    first = items[0]
    second = items[1]

    if not isinstance(first, dict) or not isinstance(second, dict):
        print("failed: message items must be dict")
        return False

    checks = [
        first.get("role") == "user",
        first.get("content") == "SKU001 多少钱",
        second.get("role") == "assistant",
        second.get("selected_module") == "price",
        second.get("route_status") == "routed",
        second.get("parse_status") == "parsed",
        second.get("handler_status") == "handoff",
        second.get("handoff_required") is True,
        second.get("handoff_ticket_id") == 789,
        second.get("handoff_ticket_no") == "HT-API-789",
    ]

    if not all(checks):
        print("failed: message content mismatch")
        pprint(items)
        return False

    return True


def check_unknown_session(
    *,
    client: TestClient,
) -> bool:
    """Check querying an unknown session returns empty list."""

    print("=" * 80)
    print("checking unknown session")

    unknown_session_id = f"unknown-{uuid4().hex[:12]}"

    response = client.get(
        ENDPOINT,
        params={
            "session_id": unknown_session_id,
            "limit": 20,
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

    return (
        payload["session_id"] == unknown_session_id
        and payload["conversation"] is None
        and payload["items"] == []
    )


def check_limit(
    *,
    client: TestClient,
    session_id: str,
) -> bool:
    """Check limit parameter."""

    print("=" * 80)
    print("checking limit")

    response = client.get(
        ENDPOINT,
        params={
            "session_id": session_id,
            "limit": 1,
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

    return payload["limit"] == 1 and len(payload["items"]) <= 1


def check_boundaries(
    *,
    client: TestClient,
) -> bool:
    """Check request validation boundaries."""

    print("=" * 80)
    print("checking boundaries")

    cases = [
        (
            {},
            422,
        ),
        (
            {
                "session_id": "",
            },
            422,
        ),
        (
            {
                "session_id": "x",
                "limit": 0,
            },
            422,
        ),
        (
            {
                "session_id": "x",
                "limit": 101,
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
    """Run Conversation API checks."""

    cleanup_test_conversations()
    session_id = seed_conversation()

    try:
        client = TestClient(app)

        results = [
            check_route_registered(),
            check_existing_conversation(
                client=client,
                session_id=session_id,
            ),
            check_unknown_session(client=client),
            check_limit(
                client=client,
                session_id=session_id,
            ),
            check_boundaries(client=client),
        ]
    finally:
        cleanup_test_conversations()

    print("=" * 80)

    if not all(results):
        print("conversation API check failed")
        return 1

    print("conversation API check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())