"""Manual handoff ticket API.

This module exposes read-only handoff ticket query endpoints.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges,
promise compensation, or update ticket resolution.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repositories.handoff_ticket_repository import HandoffTicketRepository

router = APIRouter(
    prefix="/handoff",
    tags=["handoff"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db_session),
]


@router.get("/tickets")
def list_handoff_tickets(
    session: DatabaseSession,
    status: Annotated[str | None, Query()] = None,
    selected_module: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """List handoff tickets with optional filters."""

    repository = HandoffTicketRepository(session)

    items = repository.list_tickets(
        status=status,
        selected_module=selected_module,
        limit=limit,
        offset=offset,
    )
    total = repository.count_tickets(
        status=status,
        selected_module=selected_module,
    )

    return {
        "items": [item.to_dict() for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "status": status,
            "selected_module": selected_module,
        },
    }