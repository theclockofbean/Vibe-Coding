# ruff: noqa: E402,I001
"""Check LangGraph workflow output against current Unified Agent API.

This script verifies that the new workflow skeleton remains compatible with the
existing stable API output while producing no database side effects.

It does not call an LLM, generate unsupported business answers, promise prices,
promise logistics, promise quality, promise warranty, promise returns/exchanges,
or create business commitments.
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
    create_initial_agent_state,
    detect_forbidden_commitments,
    state_to_response_payload,
)
from app.agent.workflow import run_agent_workflow
from app.core.database import get_session_factory
from app.main import app
from app.repositories import ProductRepository
from app.repositories.conversation_repository import ConversationRepository


AGENT_ENDPOINT: Final[str] = "/api/v1/agent/query"
CONVERSATION_ENDPOINT: Final[str] = "/api/v1/agent/conversation"
TEST_SOURCE_CHANNEL: Final[str] = "workflow_vs_unified_api_test"

EXPECTED_VISITED_NODES: Final[list[str]] = [
    "context",
    "intent",
    "route",
    "handler",
    "retrieval",
    "risk_control",
    "render",
]

STABLE_COMPARE_KEYS: Final[tuple[str, ...]] = (
    "selected_module",
    "route_status",
    "parse_status",
    "handler_status",
    "answer_text",
    "handoff_required",
    "source_references",
    "module_payload",
)


@dataclass(frozen=True)
class WorkflowVsApiCase:
    """One workflow-vs-API consistency case."""

    name: str
    text: str


def cleanup_test_data() -> None:
    """Delete workflow-vs-API test data."""

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


def build_cases() -> list[WorkflowVsApiCase]:
    """Build deterministic comparison cases."""

    return [
        WorkflowVsApiCase(
            name="spec_success",
            text="SKU001 螺纹是多少",
        ),
        WorkflowVsApiCase(
            name="logistics_stock_or_shipping",
            text="SKU001 有现货吗，什么时候发货",
        ),
        WorkflowVsApiCase(
            name="price_handoff",
            text="SKU001 多少钱",
        ),
        WorkflowVsApiCase(
            name="quality_handoff",
            text="SKU001 会不会生锈",
        ),
        WorkflowVsApiCase(
            name="unknown_question",
            text="你好，请问你是谁",
        ),
    ]


def make_session_id(case_name: str) -> str:
    """Create unique session ID."""

    return f"session-workflow-api-{case_name}-{uuid4().hex[:8]}"


def count_conversation_messages(session_id: str) -> int:
    """Count conversation messages for one session."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM conversation_messages
                WHERE session_id = :session_id;
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    return int(result)


def count_handoff_tickets(session_id: str) -> int:
    """Count handoff tickets for one session."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM handoff_tickets
                WHERE source_channel = :source_channel
                  AND session_id = :session_id;
                """
            ),
            {
                "source_channel": TEST_SOURCE_CHANNEL,
                "session_id": session_id,
            },
        ).scalar_one()

    return int(result)


def fetch_conversation_message_count(
    *,
    client: TestClient,
    session_id: str,
) -> int | None:
    """Fetch conversation message count through API."""

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
        return None

    payload = response.json()
    items = payload.get("items")

    if not isinstance(items, list):
        print("failed: conversation items must be list")
        pprint(payload)
        return None

    return len(items)


def call_unified_api(
    *,
    client: TestClient,
    case: WorkflowVsApiCase,
    session_id: str,
) -> dict[str, Any] | None:
    """Call current stable Unified Agent API."""

    response = client.post(
        AGENT_ENDPOINT,
        json={
            "text": case.text,
            "limit": 5,
            "source_channel": TEST_SOURCE_CHANNEL,
            "session_id": session_id,
            "user_id": "user-workflow-vs-api-test",
        },
    )

    if response.status_code != 200:
        print(f"failed: API expected 200, got {response.status_code}")
        print(response.text)
        return None

    payload = response.json()

    if not isinstance(payload, dict):
        print("failed: API payload must be dict")
        pprint(payload)
        return None

    return {
        str(key): value
        for key, value in payload.items()
    }


def run_workflow(
    *,
    case: WorkflowVsApiCase,
    session_id: str,
) -> dict[str, Any]:
    """Run LangGraph workflow skeleton for the same input."""

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        conversation_repository = ConversationRepository(session)

        initial_state = create_initial_agent_state(
            session_id=session_id,
            channel=TEST_SOURCE_CHANNEL,
            user_id="user-workflow-vs-api-test",
            user_text=case.text,
        )

        final_state = run_agent_workflow(
            initial_state=initial_state,
            product_repository=product_repository,
            conversation_repository=conversation_repository,
            limit=5,
        )

    workflow_payload = state_to_response_payload(final_state)

    return {
        "state": final_state,
        "payload": workflow_payload,
    }


def assert_no_forbidden_text(
    *,
    api_payload: dict[str, Any],
    workflow_state: dict[str, Any],
) -> bool:
    """Assert both API and workflow outputs contain no forbidden commitments."""

    api_answer_text = str(api_payload.get("answer_text", ""))
    api_final_response = str(api_payload.get("final_response", ""))

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

    joined_api_text = f"{api_answer_text}\n{api_final_response}"

    for fragment in forbidden_fragments:
        if fragment in joined_api_text:
            print(f"failed: forbidden fragment in API output: {fragment}")
            return False

    detected_in_workflow = detect_forbidden_commitments(workflow_state)

    if detected_in_workflow:
        print("failed: forbidden fragments in workflow output")
        pprint(detected_in_workflow)
        return False

    return True


def compare_stable_outputs(
    *,
    api_payload: dict[str, Any],
    workflow_payload: dict[str, Any],
) -> bool:
    """Compare stable business output fields."""

    passed = True

    for key in STABLE_COMPARE_KEYS:
        api_value = api_payload.get(key)
        workflow_value = workflow_payload.get(key)

        if api_value != workflow_value:
            print(f"failed: stable field mismatch: {key}")
            print("api:")
            pprint(api_value)
            print("workflow:")
            pprint(workflow_value)
            passed = False

    return passed


def run_case(
    *,
    client: TestClient,
    case: WorkflowVsApiCase,
) -> bool:
    """Run one comparison case."""

    print("=" * 100)
    print(f"case: {case.name}")
    print(f"text: {case.text}")

    session_id = make_session_id(case.name)

    api_payload = call_unified_api(
        client=client,
        case=case,
        session_id=session_id,
    )

    if api_payload is None:
        return False

    messages_after_api = count_conversation_messages(session_id)
    tickets_after_api = count_handoff_tickets(session_id)
    conversation_items_after_api = fetch_conversation_message_count(
        client=client,
        session_id=session_id,
    )

    workflow_result = run_workflow(
        case=case,
        session_id=session_id,
    )

    workflow_state = workflow_result["state"]
    workflow_payload = workflow_result["payload"]

    messages_after_workflow = count_conversation_messages(session_id)
    tickets_after_workflow = count_handoff_tickets(session_id)
    conversation_items_after_workflow = fetch_conversation_message_count(
        client=client,
        session_id=session_id,
    )

    print("-" * 100)
    print("api payload:")
    pprint(api_payload)
    print("-" * 100)
    print("workflow state:")
    pprint(workflow_state)
    print("-" * 100)
    print("workflow payload:")
    pprint(workflow_payload)
    print("-" * 100)
    print(
        "side effects: "
        f"messages_after_api={messages_after_api}, "
        f"messages_after_workflow={messages_after_workflow}, "
        f"tickets_after_api={tickets_after_api}, "
        f"tickets_after_workflow={tickets_after_workflow}"
    )

    metadata = workflow_state.get("metadata", {})
    visited_nodes = metadata.get("visited_nodes", [])

    api_handoff_required = bool(api_payload.get("handoff_required"))

    checks = [
        compare_stable_outputs(
            api_payload=api_payload,
            workflow_payload=workflow_payload,
        ),
        workflow_payload.get("session_id") == api_payload.get("session_id"),
        workflow_payload.get("conversation_id")
        == api_payload.get("conversation_id"),
        workflow_payload.get("human_handoff") == api_handoff_required,
        visited_nodes == EXPECTED_VISITED_NODES,
        metadata.get("workflow_started_at") is not None,
        metadata.get("workflow_finished_at") is not None,
        metadata.get("response_ready") is True,
        metadata.get("retrieval_mode") == "disabled_placeholder",
        isinstance(workflow_state.get("conversation_history"), list),
        len(workflow_state.get("conversation_history", [])) == 2,
        messages_after_api == 2,
        messages_after_workflow == messages_after_api,
        conversation_items_after_api == 2,
        conversation_items_after_workflow == conversation_items_after_api,
        tickets_after_workflow == tickets_after_api,
        assert_no_forbidden_text(
            api_payload=api_payload,
            workflow_state=workflow_state,
        ),
    ]

    if api_handoff_required:
        checks.append(tickets_after_api == 1)
        checks.append(isinstance(api_payload.get("handoff_ticket_id"), int))
        checks.append(
            isinstance(api_payload.get("handoff_ticket_no"), str)
            and str(api_payload.get("handoff_ticket_no")).startswith("HT-")
        )
        checks.append(workflow_payload.get("handoff_ticket_id") is None)
        checks.append(workflow_payload.get("handoff_ticket_no") is None)
    else:
        checks.append(tickets_after_api == 0)

    if not all(checks):
        print("failed checks:")
        for index, passed in enumerate(checks, start=1):
            if not passed:
                print(f"- check #{index} failed")
        return False

    return True


def main() -> int:
    """Run all workflow-vs-API consistency checks."""

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

    print("=" * 100)

    if not all(results):
        print("agent workflow vs unified API check failed")
        return 1

    print("agent workflow vs unified API check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())