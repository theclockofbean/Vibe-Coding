# ruff: noqa: E402,I001
"""Check ConversationRepository."""

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

from app.core.database import get_session_factory
from app.repositories.conversation_repository import (
    ConversationMessageCreate,
    ConversationRepository,
)


TEST_SOURCE_CHANNEL: Final[str] = "conversation_repository_test"


def cleanup_test_conversations() -> None:
    """Delete repository test conversations."""

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

    return f"session-repo-{uuid4().hex[:12]}"


def run_repository_checks() -> bool:
    """Run repository checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ConversationRepository(session)

        with session.begin():
            session_id = make_session_id()

            conversation = repository.get_or_create(
                session_id=session_id,
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-repo-test",
                title="repository test conversation",
                metadata={
                    "test_case": "conversation_repository",
                },
            )

            same_conversation = repository.get_or_create(
                session_id=session_id,
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-repo-test",
            )

            user_message = repository.add_message(
                ConversationMessageCreate(
                    conversation_id=conversation.id,
                    session_id=conversation.session_id,
                    role="user",
                    content="SKU001 多少钱",
                    source_channel=TEST_SOURCE_CHANNEL,
                    user_id="user-conversation-repo-test",
                    metadata={
                        "message_type": "test_user_message",
                    },
                )
            )

            assistant_message = repository.add_message(
                ConversationMessageCreate(
                    conversation_id=conversation.id,
                    session_id=conversation.session_id,
                    role="assistant",
                    content="当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。",
                    source_channel=TEST_SOURCE_CHANNEL,
                    user_id="user-conversation-repo-test",
                    selected_module="price",
                    route_status="routed",
                    parse_status="parsed",
                    handler_status="handoff",
                    handoff_required=True,
                    handoff_ticket_id=123,
                    handoff_ticket_no="HT-TEST-123",
                    source_references=[],
                    module_payload={
                        "selected_module": "price",
                        "handler_status": "handoff",
                    },
                    agent_payload={
                        "selected_module": "price",
                        "handoff_required": True,
                    },
                    metadata={
                        "message_type": "test_assistant_message",
                    },
                )
            )

            print("=" * 80)
            print("created conversation")
            pprint(conversation.to_dict())
            print("=" * 80)
            print("created messages")
            pprint(
                [
                    user_message.to_dict(),
                    assistant_message.to_dict(),
                ]
            )

            loaded_conversation = repository.get_by_session_id(session_id)
            listed_messages = repository.list_messages(
                session_id=session_id,
                limit=20,
            )
            listed_conversations = repository.list_conversations(
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-repo-test",
                status="active",
                limit=20,
                offset=0,
            )
            conversation_count = repository.count_conversations(
                source_channel=TEST_SOURCE_CHANNEL,
                user_id="user-conversation-repo-test",
                status="active",
            )

            print("=" * 80)
            print("loaded conversation")
            pprint(
                loaded_conversation.to_dict()
                if loaded_conversation is not None
                else None
            )
            print("=" * 80)
            print("listed messages")
            pprint([message.to_dict() for message in listed_messages])
            print("=" * 80)
            print("listed conversations")
            pprint([item.to_dict() for item in listed_conversations])
            print(f"conversation_count={conversation_count}")

            checks: list[bool] = []

            checks.append(same_conversation.id == conversation.id)
            checks.append(loaded_conversation is not None)

            if loaded_conversation is not None:
                checks.append(loaded_conversation.session_id == session_id)
                checks.append(loaded_conversation.message_count == 2)
                checks.append(loaded_conversation.last_user_text == "SKU001 多少钱")
                checks.append(
                    loaded_conversation.last_assistant_text
                    == "当前系统尚未接入正式价格表，不能直接给出报价。请转人工确认。"
                )
                checks.append(loaded_conversation.last_message_at is not None)

            checks.append(len(listed_messages) == 2)
            checks.append(listed_messages[0].role == "user")
            checks.append(listed_messages[1].role == "assistant")
            checks.append(listed_messages[1].selected_module == "price")
            checks.append(listed_messages[1].handoff_required is True)
            checks.append(listed_messages[1].handoff_ticket_no == "HT-TEST-123")
            checks.append(listed_messages[1].module_payload is not None)
            checks.append(listed_messages[1].agent_payload is not None)
            checks.append(any(item.id == conversation.id for item in listed_conversations))
            checks.append(conversation_count >= 1)

        return all(checks)


def main() -> int:
    """Run ConversationRepository checks."""

    cleanup_test_conversations()

    try:
        passed = run_repository_checks()
    finally:
        cleanup_test_conversations()

    print("=" * 80)

    if not passed:
        print("conversation repository check failed")
        return 1

    print("conversation repository check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())