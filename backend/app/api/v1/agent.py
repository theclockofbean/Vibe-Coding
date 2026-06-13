"""Unified agent API.

This module exposes unified agent endpoints.

It does not call an LLM, directly query products, bypass UnifiedTextQAService,
generate extra business answers, promise prices, promise logistics, promise
quality, promise warranty, promise returns/exchanges, or write data outside
controlled repository/service boundaries.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.services import (
    ConversationService,
    HandoffTicketService,
    UnifiedTextQAService,
)
from app.core.database import get_db_session
from app.repositories import ProductRepository
from app.repositories.conversation_repository import (
    Conversation,
    ConversationRepository,
)
from app.repositories.handoff_ticket_repository import HandoffTicketRepository

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db_session),
]


class UnifiedAgentQueryRequest(BaseModel):
    """Request body for unified agent query."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User query text.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum result limit passed to module services.",
    )
    source_channel: str = Field(
        default="local_test",
        min_length=1,
        max_length=64,
        description="Source channel for audit and handoff tickets.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional session ID.",
    )
    user_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional user ID.",
    )


@router.post("/query")
def query_agent(
    request: UnifiedAgentQueryRequest,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Route and answer one query through UnifiedTextQAService."""

    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="text must not be blank",
        )

    conversation = _get_or_create_conversation(
        request=request,
        session=session,
    )

    product_repository = ProductRepository(session)
    unified_service = UnifiedTextQAService(
        product_repository=product_repository,
    )

    result = unified_service.answer(
        text=text,
        limit=request.limit,
    )
    payload = result.to_response_payload()

    payload["session_id"] = conversation.session_id
    payload["conversation_id"] = conversation.id
    payload["user_message_id"] = None
    payload["assistant_message_id"] = None
    payload["handoff_ticket_id"] = None
    payload["handoff_ticket_no"] = None

    if payload.get("handoff_required") is True:
        _try_create_handoff_ticket(
            payload=payload,
            user_text=text,
            source_channel=request.source_channel,
            session_id=conversation.session_id,
            user_id=request.user_id,
            session=session,
        )

    _try_record_conversation_messages(
        payload=payload,
        conversation=conversation,
        user_text=text,
        source_channel=request.source_channel,
        user_id=request.user_id,
        session=session,
    )

    return payload


@router.get("/conversation")
def get_conversation(
    session: DatabaseSession,
    session_id: Annotated[
        str,
        Query(
            min_length=1,
            max_length=128,
            description="Conversation session ID.",
        ),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum number of messages to return.",
        ),
    ] = 20,
) -> dict[str, Any]:
    """Return conversation messages by session_id."""

    repository = ConversationRepository(session)
    service = ConversationService(repository=repository)

    conversation = repository.get_by_session_id(session_id)

    if conversation is None:
        return {
            "session_id": session_id,
            "conversation": None,
            "items": [],
            "limit": limit,
        }

    history = service.load_history(
        session_id=session_id,
        limit=limit,
    )

    return {
        "session_id": session_id,
        "conversation": conversation.to_dict(),
        "items": history,
        "limit": limit,
    }


def _get_or_create_conversation(
    *,
    request: UnifiedAgentQueryRequest,
    session: Session,
) -> Conversation:
    """Create or load conversation before answering."""

    repository = ConversationRepository(session)
    service = ConversationService(repository=repository)

    conversation = service.get_or_create_conversation(
        session_id=request.session_id,
        source_channel=request.source_channel,
        user_id=request.user_id,
    )

    session.commit()

    return conversation


def _try_create_handoff_ticket(
    *,
    payload: dict[str, Any],
    user_text: str,
    source_channel: str,
    session_id: str | None,
    user_id: str | None,
    session: Session,
) -> None:
    """Create handoff ticket and attach ticket metadata to payload."""

    try:
        repository = HandoffTicketRepository(session)
        handoff_service = HandoffTicketService(
            repository=repository,
        )
        handoff_result = handoff_service.create_from_unified_result(
            user_text=user_text,
            unified_payload=payload,
            source_channel=source_channel,
            session_id=session_id,
            user_id=user_id,
        )

        if handoff_result.created:
            session.commit()
            payload["handoff_ticket_id"] = handoff_result.ticket_id
            payload["handoff_ticket_no"] = handoff_result.ticket_no
            return

        _append_warnings(payload, handoff_result.warnings)

    except Exception:  # noqa: BLE001
        session.rollback()
        _append_warnings(payload, ["handoff ticket creation failed"])


def _try_record_conversation_messages(
    *,
    payload: dict[str, Any],
    conversation: Conversation,
    user_text: str,
    source_channel: str,
    user_id: str | None,
    session: Session,
) -> None:
    """Record user and assistant messages."""

    try:
        repository = ConversationRepository(session)
        service = ConversationService(repository=repository)

        user_message = service.record_user_message(
            conversation=conversation,
            user_text=user_text,
            source_channel=source_channel,
            user_id=user_id,
        )
        payload["user_message_id"] = user_message.id

        assistant_message = service.record_agent_response(
            conversation=conversation,
            answer_text=str(payload.get("answer_text", "")),
            agent_payload=payload,
        )
        payload["assistant_message_id"] = assistant_message.id

        session.commit()

    except Exception:  # noqa: BLE001
        session.rollback()
        payload["user_message_id"] = None
        payload["assistant_message_id"] = None
        _append_warnings(payload, ["conversation message recording failed"])


def _append_warnings(
    payload: dict[str, Any],
    warnings_to_add: list[str],
) -> None:
    """Append warnings to unified response payload."""

    existing_warnings = payload.get("warnings")

    if isinstance(existing_warnings, list):
        warnings = [str(item) for item in existing_warnings]
    else:
        warnings = []

    warnings.extend(warnings_to_add)
    payload["warnings"] = warnings