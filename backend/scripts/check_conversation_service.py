# ruff: noqa: E402,I001
"""Check ConversationService."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final
from uuid import uuid4

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.services import ConversationService
from app.core.database import get_session_factory
from app.repositories.conversation_repository import ConversationRepository


TEST_SOURCE_CHANNEL: Final[str] = "conversation_service_test"


def cleanup_test_conversations() -> None:
    """Delete service test conversations."""

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
    """Create deterministic-looking session ID."""

    return f"session-service-{uuid4().hex[:12]}"


def build_agent_payload() -> dict[str, object]:
    """Build a handoff agent payload."""

    return {
        "selected_module": "price",
        "route_status": "routed",
        "parse_status": "parsed",
        "handler_status": "handoff",
        "answer_text": "当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。",
        "handoff_required": True,
        "handoff_ticket_id": 456,
        "handoff_ticket_no": "HT-SERVICE-456",
        "source_references": [],
        "module_payload": {
            "selected_module": "price",
            "handler_status": "handoff",
        },
        "warnings": [],
        "errors": [],
    }


def run_service_checks() -> bool:
    """Run conversation service checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ConversationRepository(session)
        service = ConversationService(repository=repository)

        with session.begin():
            generated_conversation = service.get_or_create_conversation(
                session_id=None,
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-service-test",
            )

            explicit_session_id = make_session_id()
            explicit_conversation = service.get_or_create_conversation(
                session_id=explicit_session_id,
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-service-test",
            )
            same_conversation = service.get_or_create_conversation(
                session_id=explicit_session_id,
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-service-test",
            )

            user_message = service.record_user_message(
                conversation=explicit_conversation,
                user_text="SKU001 多少钱",
            )

            agent_payload = build_agent_payload()
            assistant_message = service.record_agent_response(
                conversation=explicit_conversation,
                answer_text=str(agent_payload["answer_text"]),
                agent_payload=agent_payload,
            )

            history = service.load_history(
                session_id=explicit_session_id,
                limit=20,
            )

            loaded_conversation = repository.get_by_session_id(
                explicit_session_id,
            )

            print("=" * 80)
            print("generated conversation")
            pprint(generated_conversation.to_dict())
            print("=" * 80)
            print("explicit conversation")
            pprint(explicit_conversation.to_dict())
            print("=" * 80)
            print("messages")
            pprint(
                [
                    user_message.to_dict(),
                    assistant_message.to_dict(),
                ]
            )
            print("=" * 80)
            print("history")
            pprint(history)
            print("=" * 80)
            print("loaded conversation")
            pprint(
                loaded_conversation.to_dict()
                if loaded_conversation is not None
                else None
            )

            checks: list[bool] = []

            checks.append(
                generated_conversation.session_id.startswith("session-"),
            )
            checks.append(explicit_conversation.session_id == explicit_session_id)
            checks.append(same_conversation.id == explicit_conversation.id)

            checks.append(user_message.role == "user")
            checks.append(user_message.content == "SKU001 多少钱")

            checks.append(assistant_message.role == "assistant")
            checks.append(assistant_message.selected_module == "price")
            checks.append(assistant_message.route_status == "routed")
            checks.append(assistant_message.parse_status == "parsed")
            checks.append(assistant_message.handler_status == "handoff")
            checks.append(assistant_message.handoff_required is True)
            checks.append(assistant_message.handoff_ticket_id == 456)
            checks.append(assistant_message.handoff_ticket_no == "HT-SERVICE-456")
            checks.append(assistant_message.module_payload is not None)
            checks.append(assistant_message.agent_payload is not None)

            checks.append(len(history) == 2)
            checks.append(history[0]["role"] == "user")
            checks.append(history[1]["role"] == "assistant")
            checks.append(history[1]["selected_module"] == "price")
            checks.append(history[1]["handoff_required"] is True)
            checks.append(history[1]["handoff_ticket_no"] == "HT-SERVICE-456")

            checks.append(loaded_conversation is not None)

            if loaded_conversation is not None:
                checks.append(loaded_conversation.message_count == 2)
                checks.append(
                    loaded_conversation.last_user_text == "SKU001 多少钱",
                )
                checks.append(
                    loaded_conversation.last_assistant_text
                    == agent_payload["answer_text"]
                )

        return all(checks)


def main() -> int:
    """Run ConversationService checks."""

    cleanup_test_conversations()

    try:
        passed = run_service_checks()
    finally:
        cleanup_test_conversations()

    print("=" * 80)

    if not passed:
        print("conversation service check failed")
        return 1

    print("conversation service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())