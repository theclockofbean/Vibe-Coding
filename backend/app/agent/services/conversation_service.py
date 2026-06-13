"""Conversation service.

This service manages session IDs and records conversation messages.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
decide business intent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.conversation_repository import (
    Conversation,
    ConversationMessage,
    ConversationMessageCreate,
    ConversationRepository,
)


class ConversationService:
    """Service for conversation/session management."""

    def __init__(
        self,
        *,
        repository: ConversationRepository,
    ) -> None:
        """Initialize service."""

        self._repository = repository

    def get_or_create_conversation(
        self,
        *,
        session_id: str | None,
        source_channel: str = "local_test",
        user_id: str | None = None,
    ) -> Conversation:
        """Get existing conversation or create a new one."""

        normalized_session_id = self._normalize_session_id(session_id)

        return self._repository.get_or_create(
            session_id=normalized_session_id,
            source_channel=source_channel,
            user_id=user_id,
        )

    def record_user_message(
        self,
        *,
        conversation: Conversation,
        user_text: str,
        source_channel: str | None = None,
        user_id: str | None = None,
    ) -> ConversationMessage:
        """Record one user message."""

        return self._repository.add_message(
            ConversationMessageCreate(
                conversation_id=conversation.id,
                session_id=conversation.session_id,
                role="user",
                content=user_text,
                source_channel=source_channel or conversation.source_channel,
                user_id=user_id or conversation.user_id,
            )
        )

    def record_agent_response(
        self,
        *,
        conversation: Conversation,
        answer_text: str,
        agent_payload: dict[str, object],
    ) -> ConversationMessage:
        """Record one assistant response from unified agent payload."""

        return self._repository.add_message(
            ConversationMessageCreate(
                conversation_id=conversation.id,
                session_id=conversation.session_id,
                role="assistant",
                content=answer_text,
                source_channel=conversation.source_channel,
                user_id=conversation.user_id,
                selected_module=self._optional_text(
                    agent_payload.get("selected_module"),
                ),
                route_status=self._optional_text(
                    agent_payload.get("route_status"),
                ),
                parse_status=self._optional_text(
                    agent_payload.get("parse_status"),
                ),
                handler_status=self._optional_text(
                    agent_payload.get("handler_status"),
                ),
                handoff_required=self._bool_value(
                    agent_payload.get("handoff_required"),
                ),
                handoff_ticket_id=self._optional_int(
                    agent_payload.get("handoff_ticket_id"),
                ),
                handoff_ticket_no=self._optional_text(
                    agent_payload.get("handoff_ticket_no"),
                ),
                source_references=self._list_of_dict(
                    agent_payload.get("source_references"),
                ),
                module_payload=self._optional_dict(
                    agent_payload.get("module_payload"),
                ),
                agent_payload=agent_payload,
            )
        )

    def load_history(
        self,
        *,
        session_id: str,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        """Load conversation history for ContextNode-like usage."""

        messages = self._repository.list_messages(
            session_id=session_id,
            limit=limit,
        )

        return [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "selected_module": message.selected_module,
                "route_status": message.route_status,
                "parse_status": message.parse_status,
                "handler_status": message.handler_status,
                "handoff_required": message.handoff_required,
                "handoff_ticket_id": message.handoff_ticket_id,
                "handoff_ticket_no": message.handoff_ticket_no,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ]

    @classmethod
    def _normalize_session_id(
        cls,
        session_id: str | None,
    ) -> str:
        """Return provided session_id or generate a new one."""

        if session_id is not None and session_id.strip():
            return session_id.strip()

        return cls._generate_session_id()

    @staticmethod
    def _generate_session_id() -> str:
        """Generate one local session ID."""

        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        random_part = uuid4().hex[:12]

        return f"session-{date_part}-{random_part}"

    @staticmethod
    def _optional_text(value: object) -> str | None:
        """Return optional text."""

        if value is None:
            return None

        return str(value)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        """Return optional int."""

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value

        return int(str(value))

    @staticmethod
    def _bool_value(value: object) -> bool:
        """Return boolean value."""

        if isinstance(value, bool):
            return value

        return False

    @staticmethod
    def _list_of_dict(value: object) -> list[dict[str, object]]:
        """Return list[dict[str, object]] from unknown value."""

        if not isinstance(value, list):
            return []

        result: list[dict[str, object]] = []

        for item in value:
            if isinstance(item, dict):
                result.append(
                    {
                        str(key): item_value
                        for key, item_value in item.items()
                    }
                )

        return result

    @staticmethod
    def _optional_dict(value: object) -> dict[str, object] | None:
        """Return optional dict from unknown value."""

        if value is None:
            return None

        if not isinstance(value, dict):
            return None

        return {
            str(key): item_value
            for key, item_value in value.items()
        }