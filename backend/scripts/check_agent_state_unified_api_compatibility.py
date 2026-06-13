# ruff: noqa: E402,I001
"""Check AgentState compatibility with Unified Agent API.

This script verifies that current POST /api/v1/agent/query responses can be
mapped into AgentState, combined with conversation history, and converted back
to a response payload.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

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

from app.agent.state import (
    apply_conversation_context,
    apply_risk_control,
    apply_unified_payload,
    create_initial_agent_state,
    detect_forbidden_commitments,
    state_to_response_payload,
)
from app.core.database import get_session_factory
from app.main import app


AGENT_ENDPOINT: Final[str] = "/api/v1/agent/query"
CONVERSATION_ENDPOINT: Final[str] = "/api/v1/agent/conversation"
TEST_SOURCE_CHANNEL: Final[str] = "agent_state_api_compatibility_test"


@dataclass(frozen=True)
class CompatibilityCase:
    """One AgentState compatibility case."""

    name: str
    text: str
    session_id: str | None
    expected_selected_module: str
    expected_handler_status: str
    expected_handoff_required: bool
    expected_ticket_created: bool
    expected_answer_fragments: tuple[str, ...]


def cleanup_test_data() -> None:
    """Delete compatibility test data."""

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
    """Create unique session ID."""

    return f"session-state-api-{uuid4().hex[:12]}"


def build_cases() -> list[CompatibilityCase]:
    """Build deterministic compatibility cases."""

    return [
        CompatibilityCase(
            name="spec_success_maps_to_state",
            text="SKU001 螺纹是多少",
            session_id=make_session_id(),
            expected_selected_module="spec",
            expected_handler_status="success",
            expected_handoff_required=False,
            expected_ticket_created=False,
            expected_answer_fragments=("SKU001", "螺纹规格"),
        ),
        CompatibilityCase(
            name="price_handoff_maps_to_state",
            text="SKU001 多少钱",
            session_id=make_session_id(),
            expected_selected_module="price",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=("SKU001", "不能直接给出报价"),
        ),
        CompatibilityCase(
            name="quality_handoff_generated_session_maps_to_state",
            text="SKU001 会不会生锈",
            session_id=None,
            expected_selected_module="quality",
            expected_handler_status="handoff",
            expected_handoff_required=True,
            expected_ticket_created=True,
            expected_answer_fragments=("SKU001", "不能自动承诺不生锈"),
        ),
    ]


def assert_no_forbidden_fragments(text: str) -> bool:
    """Check no unsupported commitment appears in response text."""

    forbidden_fragments = [
        "保证最低价",
        "最低价给你",
        "一定包邮",
        "保证到货",
        "今天一定发",
        "保证不坏",
        "保证不生锈",
        "保证不掉漆",
        "保证耐用",
        "能用几年",
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
        if fragment in text:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def fetch_conversation_history(
    *,
    client: TestClient,
    session_id: str,
) -> tuple[int | None, list[dict[str, Any]]]:
    """Fetch conversation history through current API."""

    response = client.get(
        CONVERSATION_ENDPOINT,
        params={
            "session_id": session_id,
            "limit": 20,
        },
    )

    if response.status_code != 200:
        print(
            "failed: conversation API expected 200, "
            f"got {response.status_code}"
        )
        print(response.text)
        return None, []

    payload = response.json()
    pprint(payload)

    conversation = payload.get("conversation")
    items = payload.get("items")

    conversation_id: int | None = None

    if isinstance(conversation, dict) and isinstance(conversation.get("id"), int):
        conversation_id = int(conversation["id"])

    if not isinstance(items, list):
        return conversation_id, []

    history: list[dict[str, Any]] = []

    for item in items:
        if isinstance(item, dict):
            history.append(
                {
                    str(key): value
                    for key, value in item.items()
                }
            )

    return conversation_id, history


def run_case(
    *,
    client: TestClient,
    case: CompatibilityCase,
) -> bool:
    """Run one compatibility case."""

    print("=" * 80)
    print(f"case: {case.name}")
    print(f"text: {case.text}")

    request_payload: dict[str, object] = {
        "text": case.text,
        "limit": 5,
        "source_channel": TEST_SOURCE_CHANNEL,
        "user_id": "user-agent-state-api-test",
    }

    if case.session_id is not None:
        request_payload["session_id"] = case.session_id

    response = client.post(
        AGENT_ENDPOINT,
        json=request_payload,
    )

    if response.status_code != 200:
        print(f"failed: agent API expected 200, got {response.status_code}")
        print(response.text)
        return False

    api_payload = response.json()
    pprint(api_payload)

    session_id = api_payload.get("session_id")

    if not isinstance(session_id, str):
        print("failed: api payload session_id must be str")
        return False

    conversation_id, conversation_history = fetch_conversation_history(
        client=client,
        session_id=session_id,
    )

    state = create_initial_agent_state(
        session_id=case.session_id,
        channel=TEST_SOURCE_CHANNEL,
        user_id="user-agent-state-api-test",
        user_text=case.text,
    )
    state = apply_conversation_context(
        state,
        conversation_id=conversation_id,
        conversation_history=conversation_history,
    )
    state = apply_unified_payload(
        state,
        payload=api_payload,
    )
    state = apply_risk_control(state)

    state_payload = state_to_response_payload(state)

    print("=" * 80)
    print("mapped AgentState")
    pprint(state)
    print("=" * 80)
    print("state response payload")
    pprint(state_payload)

    checks: list[bool] = []

    checks.append(state["session_id"] == session_id)
    checks.append(state["conversation_id"] == api_payload["conversation_id"])
    checks.append(state["conversation_id"] == conversation_id)
    checks.append(state["channel"] == TEST_SOURCE_CHANNEL)
    checks.append(state["user_id"] == "user-agent-state-api-test")
    checks.append(state["user_text"] == case.text)
    checks.append(len(state["conversation_history"]) == 2)

    checks.append(state["selected_module"] == case.expected_selected_module)
    checks.append(state["handler_status"] == case.expected_handler_status)
    checks.append(state["handoff_required"] == case.expected_handoff_required)
    checks.append(state["human_handoff"] == case.expected_handoff_required)

    checks.append(state["user_message_id"] == api_payload["user_message_id"])
    checks.append(
        state["assistant_message_id"] == api_payload["assistant_message_id"]
    )

    checks.append(state["answer_text"] == api_payload["answer_text"])
    checks.append(state_payload["answer_text"] == api_payload["answer_text"])

    if case.expected_ticket_created:
        checks.append(isinstance(state["handoff_ticket_id"], int))
        checks.append(
            isinstance(state["handoff_ticket_no"], str)
            and state["handoff_ticket_no"].startswith("HT-")
        )
        checks.append(
            state_payload["handoff_ticket_no"]
            == api_payload["handoff_ticket_no"]
        )
    else:
        checks.append(state.get("handoff_ticket_id") is None)
        checks.append(state.get("handoff_ticket_no") is None)

    answer_text = str(api_payload["answer_text"])

    for fragment in case.expected_answer_fragments:
        checks.append(fragment in answer_text)

    checks.append(assert_no_forbidden_fragments(answer_text))
    checks.append(detect_forbidden_commitments(state) == [])

    checks.append(state_payload["selected_module"] == api_payload["selected_module"])
    checks.append(state_payload["route_status"] == api_payload["route_status"])
    checks.append(state_payload["parse_status"] == api_payload["parse_status"])
    checks.append(state_payload["handler_status"] == api_payload["handler_status"])
    checks.append(
        state_payload["handoff_required"] == api_payload["handoff_required"]
    )
    checks.append(
        state_payload["user_message_id"] == api_payload["user_message_id"]
    )
    checks.append(
        state_payload["assistant_message_id"]
        == api_payload["assistant_message_id"]
    )

    if not all(checks):
        print("failed checks:")
        for index, passed in enumerate(checks, start=1):
            if not passed:
                print(f"- check #{index} failed")
        return False

    return True


def main() -> int:
    """Run AgentState Unified Agent API compatibility checks."""

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
        print("agent state unified API compatibility check failed")
        return 1

    print("agent state unified API compatibility check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())