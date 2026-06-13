"""Repository for manual handoff tickets.

This repository only reads and writes handoff_tickets rows.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
decide whether a ticket should be created.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeAlias

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

HandoffTicketStatus: TypeAlias = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
    "cancelled",
]

HandoffTicketPriority: TypeAlias = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]


@dataclass(frozen=True)
class HandoffTicketCreate:
    """Data required to create one handoff ticket."""

    ticket_no: str
    user_text: str
    handoff_reason: str
    status: HandoffTicketStatus = "open"
    priority: HandoffTicketPriority = "normal"
    source_channel: str | None = "local_test"
    session_id: str | None = None
    user_id: str | None = None
    selected_module: str | None = None
    route_status: str | None = None
    route_confidence: float | None = None
    candidate_modules: list[str] | None = None
    matched_signals: list[str] | None = None
    parse_status: str | None = None
    handler_status: str | None = None
    answer_text: str | None = None
    source_references: list[dict[str, object]] | None = None
    module_payload: dict[str, object] | None = None
    risk_reasons: list[str] | None = None
    assigned_to: str | None = None
    resolution_note: str | None = None


@dataclass(frozen=True)
class HandoffTicket:
    """One handoff ticket row."""

    id: int
    ticket_no: str
    status: str
    priority: str
    source_channel: str | None
    session_id: str | None
    user_id: str | None
    user_text: str
    selected_module: str | None
    route_status: str | None
    route_confidence: float | None
    candidate_modules: list[str]
    matched_signals: list[str]
    parse_status: str | None
    handler_status: str | None
    handoff_reason: str
    answer_text: str | None
    source_references: list[dict[str, object]]
    module_payload: dict[str, object] | None
    risk_reasons: list[str]
    assigned_to: str | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    def to_dict(self) -> dict[str, object]:
        """Return serializable dictionary."""

        return {
            "id": self.id,
            "ticket_no": self.ticket_no,
            "status": self.status,
            "priority": self.priority,
            "source_channel": self.source_channel,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_text": self.user_text,
            "selected_module": self.selected_module,
            "route_status": self.route_status,
            "route_confidence": self.route_confidence,
            "candidate_modules": self.candidate_modules,
            "matched_signals": self.matched_signals,
            "parse_status": self.parse_status,
            "handler_status": self.handler_status,
            "handoff_reason": self.handoff_reason,
            "answer_text": self.answer_text,
            "source_references": self.source_references,
            "module_payload": self.module_payload,
            "risk_reasons": self.risk_reasons,
            "assigned_to": self.assigned_to,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": (
                self.resolved_at.isoformat()
                if self.resolved_at is not None
                else None
            ),
        }


class HandoffTicketRepository:
    """Database repository for handoff_tickets."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        """Initialize repository."""

        self._session = session

    def create(
        self,
        ticket: HandoffTicketCreate,
    ) -> HandoffTicket:
        """Create one handoff ticket."""

        row = self._session.execute(
            text(
                """
                INSERT INTO handoff_tickets (
                    ticket_no,
                    status,
                    priority,
                    source_channel,
                    session_id,
                    user_id,
                    user_text,
                    selected_module,
                    route_status,
                    route_confidence,
                    candidate_modules,
                    matched_signals,
                    parse_status,
                    handler_status,
                    handoff_reason,
                    answer_text,
                    source_references,
                    module_payload,
                    risk_reasons,
                    assigned_to,
                    resolution_note
                )
                VALUES (
                    :ticket_no,
                    :status,
                    :priority,
                    :source_channel,
                    :session_id,
                    :user_id,
                    :user_text,
                    :selected_module,
                    :route_status,
                    :route_confidence,
                    CAST(:candidate_modules AS jsonb),
                    CAST(:matched_signals AS jsonb),
                    :parse_status,
                    :handler_status,
                    :handoff_reason,
                    :answer_text,
                    CAST(:source_references AS jsonb),
                    CAST(:module_payload AS jsonb),
                    CAST(:risk_reasons AS jsonb),
                    :assigned_to,
                    :resolution_note
                )
                RETURNING *;
                """
            ),
            {
                "ticket_no": ticket.ticket_no,
                "status": ticket.status,
                "priority": ticket.priority,
                "source_channel": ticket.source_channel,
                "session_id": ticket.session_id,
                "user_id": ticket.user_id,
                "user_text": ticket.user_text,
                "selected_module": ticket.selected_module,
                "route_status": ticket.route_status,
                "route_confidence": ticket.route_confidence,
                "candidate_modules": self._json_dumps(
                    ticket.candidate_modules or [],
                ),
                "matched_signals": self._json_dumps(
                    ticket.matched_signals or [],
                ),
                "parse_status": ticket.parse_status,
                "handler_status": ticket.handler_status,
                "handoff_reason": ticket.handoff_reason,
                "answer_text": ticket.answer_text,
                "source_references": self._json_dumps(
                    ticket.source_references or [],
                ),
                "module_payload": self._json_dumps_optional(
                    ticket.module_payload,
                ),
                "risk_reasons": self._json_dumps(ticket.risk_reasons or []),
                "assigned_to": ticket.assigned_to,
                "resolution_note": ticket.resolution_note,
            },
        ).mappings().one()

        return self._row_to_ticket(row)

    def list_tickets(
        self,
        *,
        status: str | None = None,
        selected_module: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[HandoffTicket]:
        """List handoff tickets with optional filters."""

        rows = self._session.execute(
            text(
                """
                SELECT *
                FROM handoff_tickets
                WHERE (
                    CAST(:status AS VARCHAR) IS NULL
                    OR status = CAST(:status AS VARCHAR)
                )
                  AND (
                    CAST(:selected_module AS VARCHAR) IS NULL
                    OR selected_module = CAST(:selected_module AS VARCHAR)
                  )
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                OFFSET :offset;
                """
            ),
            {
                "status": status,
                "selected_module": selected_module,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

        return [self._row_to_ticket(row) for row in rows]

    def count_tickets(
        self,
        *,
        status: str | None = None,
        selected_module: str | None = None,
    ) -> int:
        """Count handoff tickets with optional filters."""

        count = self._session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM handoff_tickets
                WHERE (
                    CAST(:status AS VARCHAR) IS NULL
                    OR status = CAST(:status AS VARCHAR)
                )
                  AND (
                    CAST(:selected_module AS VARCHAR) IS NULL
                    OR selected_module = CAST(:selected_module AS VARCHAR)
                  );
                """
            ),
            {
                "status": status,
                "selected_module": selected_module,
            },
        ).scalar_one()

        return int(count)

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
    def _row_to_ticket(
        cls,
        row: RowMapping,
    ) -> HandoffTicket:
        """Convert a database row to HandoffTicket."""

        return HandoffTicket(
            id=int(row["id"]),
            ticket_no=str(row["ticket_no"]),
            status=str(row["status"]),
            priority=str(row["priority"]),
            source_channel=cls._optional_text(row["source_channel"]),
            session_id=cls._optional_text(row["session_id"]),
            user_id=cls._optional_text(row["user_id"]),
            user_text=str(row["user_text"]),
            selected_module=cls._optional_text(row["selected_module"]),
            route_status=cls._optional_text(row["route_status"]),
            route_confidence=cls._optional_float(row["route_confidence"]),
            candidate_modules=cls._list_of_text(row["candidate_modules"]),
            matched_signals=cls._list_of_text(row["matched_signals"]),
            parse_status=cls._optional_text(row["parse_status"]),
            handler_status=cls._optional_text(row["handler_status"]),
            handoff_reason=str(row["handoff_reason"]),
            answer_text=cls._optional_text(row["answer_text"]),
            source_references=cls._list_of_dict(row["source_references"]),
            module_payload=cls._optional_dict(row["module_payload"]),
            risk_reasons=cls._list_of_text(row["risk_reasons"]),
            assigned_to=cls._optional_text(row["assigned_to"]),
            resolution_note=cls._optional_text(row["resolution_note"]),
            created_at=cls._datetime_value(row["created_at"]),
            updated_at=cls._datetime_value(row["updated_at"]),
            resolved_at=cls._optional_datetime(row["resolved_at"]),
        )

    @staticmethod
    def _optional_text(value: object) -> str | None:
        """Return optional text."""

        if value is None:
            return None

        return str(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        """Return optional float."""

        if value is None:
            return None

        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, int | float):
            return float(value)

        return float(str(value))

    @classmethod
    def _list_of_text(cls, value: object) -> list[str]:
        """Return list[str] from json-like value."""

        loaded = cls._load_json_if_needed(value)

        if not isinstance(loaded, list):
            return []

        return [str(item) for item in loaded]

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