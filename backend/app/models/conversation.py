"""Conversation session and message ORM models.

A conversation session stores channel-level metadata, while each individual
user, assistant, human, or system message is stored as a separate row.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

SESSION_SOURCE_CHANNELS: Final[tuple[str, ...]] = (
    "local_debug",
    "api_test",
    "evaluation",
)

SESSION_STATUSES: Final[tuple[str, ...]] = (
    "active",
    "closed",
    "handoff",
    "failed",
)

MESSAGE_ROLES: Final[tuple[str, ...]] = (
    "user",
    "assistant",
    "human",
    "system",
)

MESSAGE_INTENTS: Final[tuple[str, ...]] = (
    "spec",
    "quality",
    "price",
    "logistics",
    "escalation",
    "unknown",
)


def _as_sql_values(values: tuple[str, ...]) -> str:
    """Convert trusted constant values into a SQL CHECK value list."""

    return ", ".join(f"'{value}'" for value in values)


class ConversationSession(TimestampMixin, Base):
    """Represent one complete conversation session."""

    __tablename__ = "conversation_sessions"

    __table_args__ = (
        CheckConstraint(
            f"source_channel IN ({_as_sql_values(SESSION_SOURCE_CHANNELS)})",
            name="source_channel_allowed",
        ),
        CheckConstraint(
            f"status IN ({_as_sql_values(SESSION_STATUSES)})",
            name="status_allowed",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ended_at_not_before_started_at",
        ),
        UniqueConstraint(
            "session_id",
            name="uq_conversation_sessions_session_id",
        ),
        Index(
            "ix_conversation_sessions_source_channel",
            "source_channel",
        ),
        Index(
            "ix_conversation_sessions_status",
            "status",
        ),
        Index(
            "ix_conversation_sessions_started_at",
            "started_at",
        ),
        Index(
            "ix_conversation_sessions_external_user_id",
            "external_user_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        default=uuid4,
    )

    source_channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="local_debug",
        server_default="local_debug",
    )

    external_conversation_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    external_user_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationMessage.created_at",
    )


class ConversationMessage(TimestampMixin, Base):
    """Represent one message inside a conversation session."""

    __tablename__ = "conversation_messages"

    __table_args__ = (
        CheckConstraint(
            f"role IN ({_as_sql_values(MESSAGE_ROLES)})",
            name="role_allowed",
        ),
        CheckConstraint(
            "btrim(content) <> ''",
            name="content_not_blank",
        ),
        CheckConstraint(
            (
                "primary_intent IS NULL "
                f"OR primary_intent IN ({_as_sql_values(MESSAGE_INTENTS)})"
            ),
            name="primary_intent_allowed",
        ),
        CheckConstraint(
            (
                "intent_confidence IS NULL "
                "OR (intent_confidence >= 0 AND intent_confidence <= 1)"
            ),
            name="intent_confidence_range",
        ),
        CheckConstraint(
            "processing_time_ms IS NULL OR processing_time_ms >= 0",
            name="processing_time_ms_non_negative",
        ),
        CheckConstraint(
            (
                "handoff_required = false "
                "OR (handoff_reason IS NOT NULL "
                "AND btrim(handoff_reason) <> '')"
            ),
            name="handoff_reason_required",
        ),
        UniqueConstraint(
            "message_id",
            name="uq_conversation_messages_message_id",
        ),
        Index(
            "ix_conversation_messages_session_id",
            "session_id",
        ),
        Index(
            "ix_conversation_messages_primary_intent",
            "primary_intent",
        ),
        Index(
            "ix_conversation_messages_handoff_required",
            "handoff_required",
        ),
        Index(
            "ix_conversation_messages_created_at",
            "created_at",
        ),
        Index(
            "ix_conversation_messages_session_created_at",
            "session_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        default=uuid4,
    )

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "conversation_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    primary_intent: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    secondary_intents: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::varchar[]"),
    )

    intent_confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    handler_name: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    handoff_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    handoff_reason: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    source_references: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    processing_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    session: Mapped[ConversationSession] = relationship(
        back_populates="messages",
    )


__all__ = [
    "ConversationMessage",
    "ConversationSession",
    "MESSAGE_INTENTS",
    "MESSAGE_ROLES",
    "SESSION_SOURCE_CHANNELS",
    "SESSION_STATUSES",
]