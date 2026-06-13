"""Repository for conversations and conversation messages.

This repository only reads and writes conversations / conversation_messages.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
decide business intent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

ConversationStatus: TypeAlias = Literal[
    "active",
    "closed",
    "archived",
]

ConversationRole: TypeAlias = Literal[
    "user",
    "assistant",
    "system",
    "tool",
]


@dataclass(frozen=True)
class ConversationCreate:
    """Data required to create a conversation."""

    session_id: str
    source_channel: str = "local_test"
    user_id: str | None = None
    title: str | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class Conversation:
    """One conversation row."""

    id: int
    session_id: str
    source_channel: str
    user_id: str | None
    status: str
    title: str | None
    last_user_text: str | None
    last_assistant_text: str | None
    message_count: int
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None

    def to_dict(self) -> dict[str, object]:
        """Return serializable dictionary."""

        return {
            "id": self.id,
            "session_id": self.session_id,
            "source_channel": self.source_channel,
            "user_id": self.user_id,
            "status": self.status,
            "title": self.title,
            "last_user_text": self.last_user_text,
            "last_assistant_text": self.last_assistant_text,
            "message_count": self.message_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_message_at": (
                self.last_message_at.isoformat()
                if self.last_message_at is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ConversationMessageCreate:
    """Data required to create a conversation message."""

    conversation_id: int
    session_id: str
    role: ConversationRole
    content: str
    source_channel: str = "local_test"
    user_id: str | None = None
    selected_module: str | None = None
    route_status: str | None = None
    parse_status: str | None = None
    handler_status: str | None = None
    handoff_required: bool = False
    handoff_ticket_id: int | None = None
    handoff_ticket_no: str | None = None
    source_references: list[dict[str, object]] | None = None
    module_payload: dict[str, object] | None = None
    agent_payload: dict[str, object] | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class ConversationMessage:
    """One conversation_messages row."""

    id: int
    conversation_id: int
    session_id: str
    role: str
    content: str
    source_channel: str
    user_id: str | None
    selected_module: str | None
    route_status: str | None
    parse_status: str | None
    handler_status: str | None
    handoff_required: bool
    handoff_ticket_id: int | None
    handoff_ticket_no: str | None
    source_references: list[dict[str, object]]
    module_payload: dict[str, object] | None
    agent_payload: dict[str, object] | None
    metadata: dict[str, object]
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        """Return serializable dictionary."""

        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "source_channel": self.source_channel,
            "user_id": self.user_id,
            "selected_module": self.selected_module,
            "route_status": self.route_status,
            "parse_status": self.parse_status,
            "handler_status": self.handler_status,
            "handoff_required": self.handoff_required,
            "handoff_ticket_id": self.handoff_ticket_id,
            "handoff_ticket_no": self.handoff_ticket_no,
            "source_references": self.source_references,
            "module_payload": self.module_payload,
            "agent_payload": self.agent_payload,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class ConversationRepository:
    """Database repository for conversations."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        """Initialize repository."""

        self._session = session

    def get_by_session_id(
        self,
        session_id: str,
    ) -> Conversation | None:
        """Get one conversation by session_id."""

        row = self._session.execute(
            text(
                """
                SELECT *
                FROM conversations
                WHERE session_id = :session_id
                LIMIT 1;
                """
            ),
            {
                "session_id": session_id,
            },
        ).mappings().first()

        if row is None:
            return None

        return self._row_to_conversation(row)

    def get_or_create(
        self,
        *,
        session_id: str,
        source_channel: str = "local_test",
        user_id: str | None = None,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Conversation:
        """Get existing conversation or create a new one."""

        row = self._session.execute(
            text(
                """
                INSERT INTO conversations (
                    session_id,
                    source_channel,
                    user_id,
                    title,
                    metadata
                )
                VALUES (
                    :session_id,
                    :source_channel,
                    :user_id,
                    :title,
                    CAST(:metadata AS jsonb)
                )
                ON CONFLICT (session_id)
                DO UPDATE SET
                    source_channel = EXCLUDED.source_channel,
                    user_id = COALESCE(EXCLUDED.user_id, conversations.user_id),
                    title = COALESCE(conversations.title, EXCLUDED.title)
                RETURNING *;
                """
            ),
            {
                "session_id": session_id,
                "source_channel": source_channel,
                "user_id": user_id,
                "title": title,
                "metadata": self._json_dumps(metadata or {}),
            },
        ).mappings().one()

        return self._row_to_conversation(row)

    def add_message(
        self,
        message: ConversationMessageCreate,
    ) -> ConversationMessage:
        """Add one message and update conversation summary fields."""

        row = self._session.execute(
            text(
                """
                INSERT INTO conversation_messages (
                    conversation_id,
                    session_id,
                    role,
                    content,
                    source_channel,
                    user_id,
                    selected_module,
                    route_status,
                    parse_status,
                    handler_status,
                    handoff_required,
                    handoff_ticket_id,
                    handoff_ticket_no,
                    source_references,
                    module_payload,
                    agent_payload,
                    metadata
                )
                VALUES (
                    :conversation_id,
                    :session_id,
                    :role,
                    :content,
                    :source_channel,
                    :user_id,
                    :selected_module,
                    :route_status,
                    :parse_status,
                    :handler_status,
                    :handoff_required,
                    :handoff_ticket_id,
                    :handoff_ticket_no,
                    CAST(:source_references AS jsonb),
                    CAST(:module_payload AS jsonb),
                    CAST(:agent_payload AS jsonb),
                    CAST(:metadata AS jsonb)
                )
                RETURNING *;
                """
            ),
            {
                "conversation_id": message.conversation_id,
                "session_id": message.session_id,
                "role": message.role,
                "content": message.content,
                "source_channel": message.source_channel,
                "user_id": message.user_id,
                "selected_module": message.selected_module,
                "route_status": message.route_status,
                "parse_status": message.parse_status,
                "handler_status": message.handler_status,
                "handoff_required": message.handoff_required,
                "handoff_ticket_id": message.handoff_ticket_id,
                "handoff_ticket_no": message.handoff_ticket_no,
                "source_references": self._json_dumps(
                    message.source_references or [],
                ),
                "module_payload": self._json_dumps_optional(
                    message.module_payload,
                ),
                "agent_payload": self._json_dumps_optional(
                    message.agent_payload,
                ),
                "metadata": self._json_dumps(message.metadata or {}),
            },
        ).mappings().one()

        self._update_conversation_after_message(
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
        )

        return self._row_to_message(row)

    def list_messages(
        self,
        *,
        session_id: str,
        limit: int = 20,
    ) -> list[ConversationMessage]:
        """List recent messages by session_id in chronological order."""

        rows = self._session.execute(
            text(
                """
                SELECT *
                FROM (
                    SELECT *
                    FROM conversation_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                ) AS recent_messages
                ORDER BY created_at ASC, id ASC;
                """
            ),
            {
                "session_id": session_id,
                "limit": limit,
            },
        ).mappings().all()

        return [self._row_to_message(row) for row in rows]

    def list_conversations(
        self,
        *,
        source_channel: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        """List conversations with optional filters."""

        rows = self._session.execute(
            text(
                """
                SELECT *
                FROM conversations
                WHERE (
                    CAST(:source_channel AS VARCHAR) IS NULL
                    OR source_channel = CAST(:source_channel AS VARCHAR)
                )
                  AND (
                    CAST(:user_id AS VARCHAR) IS NULL
                    OR user_id = CAST(:user_id AS VARCHAR)
                  )
                  AND (
                    CAST(:status AS VARCHAR) IS NULL
                    OR status = CAST(:status AS VARCHAR)
                  )
                ORDER BY last_message_at DESC NULLS LAST, updated_at DESC, id DESC
                LIMIT :limit
                OFFSET :offset;
                """
            ),
            {
                "source_channel": source_channel,
                "user_id": user_id,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

        return [self._row_to_conversation(row) for row in rows]

    def count_conversations(
        self,
        *,
        source_channel: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count conversations with optional filters."""

        count = self._session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM conversations
                WHERE (
                    CAST(:source_channel AS VARCHAR) IS NULL
                    OR source_channel = CAST(:source_channel AS VARCHAR)
                )
                  AND (
                    CAST(:user_id AS VARCHAR) IS NULL
                    OR user_id = CAST(:user_id AS VARCHAR)
                  )
                  AND (
                    CAST(:status AS VARCHAR) IS NULL
                    OR status = CAST(:status AS VARCHAR)
                  );
                """
            ),
            {
                "source_channel": source_channel,
                "user_id": user_id,
                "status": status,
            },
        ).scalar_one()

        return int(count)

    def _update_conversation_after_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
    ) -> None:
        """Update conversation summary fields after a new message."""

        self._session.execute(
            text(
                """
                UPDATE conversations
                SET
                    message_count = message_count + 1,
                    last_message_at = NOW(),
                    last_user_text = CASE
                        WHEN CAST(:role AS VARCHAR) = 'user'
                        THEN :content
                        ELSE last_user_text
                    END,
                    last_assistant_text = CASE
                        WHEN CAST(:role AS VARCHAR) = 'assistant'
                        THEN :content
                        ELSE last_assistant_text
                    END
                WHERE id = :conversation_id;
                """
            ),
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            },
        )

    @staticmethod
    def _json_dumps(value: object) -> str:
        """Serialize JSON value."""

        return json.dumps(
            value,
            ensure_ascii=False,
        )

    @staticmethod
    def _json_dumps_optional(value: object | None) -> str | None:
        """Serialize optional JSON value."""

        if value is None:
            return None

        return json.dumps(
            value,
            ensure_ascii=False,
        )

    @classmethod
    def _row_to_conversation(
        cls,
        row: RowMapping,
    ) -> Conversation:
        """Convert row mapping to Conversation."""

        return Conversation(
            id=int(row["id"]),
            session_id=str(row["session_id"]),
            source_channel=str(row["source_channel"]),
            user_id=cls._optional_text(row["user_id"]),
            status=str(row["status"]),
            title=cls._optional_text(row["title"]),
            last_user_text=cls._optional_text(row["last_user_text"]),
            last_assistant_text=cls._optional_text(row["last_assistant_text"]),
            message_count=int(row["message_count"]),
            metadata=cls._dict_value(row["metadata"]),
            created_at=cls._datetime_value(row["created_at"]),
            updated_at=cls._datetime_value(row["updated_at"]),
            last_message_at=cls._optional_datetime(row["last_message_at"]),
        )

    @classmethod
    def _row_to_message(
        cls,
        row: RowMapping,
    ) -> ConversationMessage:
        """Convert row mapping to ConversationMessage."""

        return ConversationMessage(
            id=int(row["id"]),
            conversation_id=int(row["conversation_id"]),
            session_id=str(row["session_id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            source_channel=str(row["source_channel"]),
            user_id=cls._optional_text(row["user_id"]),
            selected_module=cls._optional_text(row["selected_module"]),
            route_status=cls._optional_text(row["route_status"]),
            parse_status=cls._optional_text(row["parse_status"]),
            handler_status=cls._optional_text(row["handler_status"]),
            handoff_required=bool(row["handoff_required"]),
            handoff_ticket_id=cls._optional_int(row["handoff_ticket_id"]),
            handoff_ticket_no=cls._optional_text(row["handoff_ticket_no"]),
            source_references=cls._list_of_dict(row["source_references"]),
            module_payload=cls._optional_dict(row["module_payload"]),
            agent_payload=cls._optional_dict(row["agent_payload"]),
            metadata=cls._dict_value(row["metadata"]),
            created_at=cls._datetime_value(row["created_at"]),
        )

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

        return _safe_int_or_none(value)

    @classmethod
    def _dict_value(cls, value: object) -> dict[str, object]:
        """Return dict from json-like value."""

        loaded = cls._load_json_if_needed(value)

        if not isinstance(loaded, dict):
            return {}

        return {
            str(key): item_value
            for key, item_value in loaded.items()
        }

    @classmethod
    def _optional_dict(
        cls,
        value: object,
    ) -> dict[str, object] | None:
        """Return optional dict from json-like value."""

        loaded = cls._load_json_if_needed(value)

        if loaded is None:
            return None

        if not isinstance(loaded, dict):
            return None

        return {
            str(key): item_value
            for key, item_value in loaded.items()
        }

    @classmethod
    def _list_of_dict(cls, value: object) -> list[dict[str, object]]:
        """Return list[dict[str, object]] from json-like value."""

        loaded = cls._load_json_if_needed(value)

        if not isinstance(loaded, list):
            return []

        result: list[dict[str, object]] = []

        for item in loaded:
            if isinstance(item, dict):
                result.append(
                    {
                        str(key): item_value
                        for key, item_value in item.items()
                    }
                )

        return result

    @staticmethod
    def _load_json_if_needed(value: object) -> object:
        """Load JSON string if needed."""

        if value is None:
            return None

        if isinstance(value, str):
            return json.loads(value)

        return value

    @staticmethod
    def _datetime_value(value: object) -> datetime:
        """Return datetime value."""

        if not isinstance(value, datetime):
            msg = f"expected datetime, got {type(value)!r}"
            raise TypeError(msg)

        return value

    @classmethod
    def _optional_datetime(cls, value: object) -> datetime | None:
        """Return optional datetime value."""

        if value is None:
            return None

        return cls._datetime_value(value)

def _safe_int_or_none(
    value: object,
) -> int | None:
    """Safely convert database scalar to optional int."""

    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.strip():
        return int(value)

    return None

