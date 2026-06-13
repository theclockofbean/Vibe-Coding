# ruff: noqa: E402,I001
"""Check Unified Agent API conversation integration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
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


AGENT_ENDPOINT: Final[str] = "/api/v1/agent/query"
CONVERSATION_ENDPOINT: Final[str] = "/api/v1/agent/conversation"
TEST_SOURCE_CHANNEL: Final[str] = "conversation_integration_test"


@dataclass(frozen=True)
class ConversationIntegrationCase:
    """One unified agent conversation integration case."""

    name: str
    text: str
    session_id: str | None
    expected_selected_module: str | None
    expected_handler_status: str
    expected_handoff_required: bool
    expected_ticket_created: bool
    expected_answer_fragments: tuple[str, ...]


def cleanup_test_data() -> None:
    """Delete integration test data."""

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


def make_session_id() -> str:
    """Create unique test session ID."""

    return f"session-conversation-integration-{uuid4().hex[:12]}"


def build_cases() -> list[ConversationIntegrationCase]:
    """Build deterministic integration cases."""

    return [
        ConversationIntegrationCase(
            name="spec_records_conversation_without_ticket",
            text="SKU001 螺纹是多少",
            session_id=make_session_id(),
            expected_selected_module="spec",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_ticket_created=False,
            expected_answer_fragments=("SKU001", "螺纹规格"),
        ),
        ConversationIntegrationCase(
            name="price_records_conversation_with_ticket",
            text="SKU001 多少钱",
            session_id=make_session_id(),
            expected_selected_module="price",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=("SKU001", "不能直接给出报价"),
        ),
        ConversationIntegrationCase(
            name="generated_session_id_records_conversation",
            text="SKU001 会不会生锈",
            session_id=None,
            expected_selected_module="quality",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=("SKU001", "不能自动承诺不生锈"),
        ),
    ]


def assert_agent_response_shape(payload: dict[str, Any]) -> bool:
    """Check unified agent response shape."""

    required_keys = {
        "selected_module",
        "route_status",
        "parse_status",
        "handler_status",
        "answer_text",
        "handoff_required",
        "session_id",
        "conversation_id",
        "user_message_id",
        "assistant_message_id",
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
    """Check no unsupported commitment appears in answer."""

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
            print(f"failed: forbidden fragment in answer_text: {fragment}")
            return False

    return True


def assert_conversation_history(
    *,
    client: TestClient,
    session_id: str,
    expected_text: str,
    payload: dict[str, Any],
) -> bool:
    """Check GET /agent/conversation returns recorded messages."""

    response = client.get(
        CONVERSATION_ENDPOINT,
        params={
            "session_id": session_id,
            "limit": 20,
        },
    )

    if response.status_code != 200:
        print(f"failed: conversation GET expected 200, got {response.status_code}")
        print(response.text)
        return False

    history_payload = response.json()
    pprint(history_payload)

    if history_payload.get("session_id") != session_id:
        print("failed: session_id echo mismatch")
        return False

    conversation = history_payload.get("conversation")
    items = history_payload.get("items")

    if not isinstance(conversation, dict):
        print("failed: conversation must be dict")
        return False

    if not isinstance(items, list):
        print("failed: items must be list")
        return False

    if len(items) != 2:
        print("failed: expected exactly 2 messages")
        return False

    user_message = items[0]
    assistant_message = items[1]

    if not isinstance(user_message, dict) or not isinstance(assistant_message, dict):
        print("failed: messages must be dict")
        return False

    checks = [
        conversation.get("id") == payload["conversation_id"],
        conversation.get("message_count") == 2,
        conversation.get("last_user_text") == expected_text,
        conversation.get("last_assistant_text") == payload["answer_text"],
        user_message.get("id") == payload["user_message_id"],
        user_message.get("role") == "user",
        user_message.get("content") == expected_text,
        assistant_message.get("id") == payload["assistant_message_id"],
        assistant_message.get("role") == "assistant",
        assistant_message.get("content") == payload["answer_text"],
        assistant_message.get("selected_module") == payload["selected_module"],
        assistant_message.get("route_status") == payload["route_status"],
        assistant_message.get("parse_status") == payload["parse_status"],
        assistant_message.get("handler_status") == payload["handler_status"],
        assistant_message.get("handoff_required") == payload["handoff_required"],
        assistant_message.get("handoff_ticket_id") == payload["handoff_ticket_id"],
        assistant_message.get("handoff_ticket_no") == payload["handoff_ticket_no"],
    ]

    if not all(checks):
        print("failed: conversation history mismatch")
        print("conversation:")
        pprint(conversation)
        print("items:")
        pprint(items)
        print("agent payload:")
        pprint(payload)
        return False

    return True


def run_case(
    *,
    client: TestClient,
    case: ConversationIntegrationCase,
) -> bool:
    """Run one integration case."""

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"text: {case.text}")

    request_payload: dict[str, object] = {
        "text": case.text,
        "limit": 5,
        "source_channel": TEST_SOURCE_CHANNEL,
        "user_id": "user-conversation-integration-test",
    }

    if case.session_id is not None:
        request_payload["session_id"] = case.session_id

    response = client.post(
        AGENT_ENDPOINT,
        json=request_payload,
    )

    if response.status_code != 200:
        print(f"failed: expected 200, got {response.status_code}")
        print(response.text)
        return False

    payload = response.json()
    pprint(payload)

    if not assert_agent_response_shape(payload):
        return False

    checks: list[bool] = []

    checks.append(payload["selected_module"] == case.expected_selected_module)
    checks.append(payload["handler_status"] == case.expected_handler_status)
    checks.append(payload["handoff_required"] == case.expected_handoff_required)
    checks.append(isinstance(payload["session_id"], str))
    checks.append(isinstance(payload["conversation_id"], int))
    checks.append(isinstance(payload["user_message_id"], int))
    checks.append(isinstance(payload["assistant_message_id"], int))

    if case.session_id is not None:
        checks.append(payload["session_id"] == case.session_id)
    else:
        checks.append(str(payload["session_id"]).startswith("session-"))

    if case.expected_ticket_created:
        checks.append(isinstance(payload["handoff_ticket_id"], int))
        checks.append(
            isinstance(payload["handoff_ticket_no"], str)
            and str(payload["handoff_ticket_no"]).startswith("HT-")
        )
    else:
        checks.append(payload["handoff_ticket_id"] is None)
        checks.append(payload["handoff_ticket_no"] is None)

    answer_text = str(payload["answer_text"])

    for fragment in case.expected_answer_fragments:
        checks.append(fragment in answer_text)

    checks.append(assert_no_forbidden_fragments(answer_text))

    checks.append(
        assert_conversation_history(
            client=client,
            session_id=str(payload["session_id"]),
            expected_text=case.text,
            payload=payload,
        )
    )

    return all(checks)


def main() -> int:
    """Run unified agent conversation integration checks."""

    cleanup_test_data()

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
        cleanup_test_data()

    print("=" * 80)

    if not all(results):
        print("unified agent conversation integration check failed")
        return 1

    print("unified agent conversation integration check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())