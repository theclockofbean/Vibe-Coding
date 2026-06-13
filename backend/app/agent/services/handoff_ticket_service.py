"""Service for creating manual handoff tickets.

This service creates database tickets from unified agent responses.

It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, promise
compensation, or decide final human resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.repositories.handoff_ticket_repository import (
    HandoffTicket,
    HandoffTicketCreate,
    HandoffTicketRepository,
)


@dataclass(frozen=True)
class HandoffTicketResult:
    """Result of trying to create one handoff ticket."""

    created: bool
    ticket: HandoffTicket | None
    warnings: list[str]
    errors: list[str]

    @property
    def ticket_id(self) -> int | None:
        """Return ticket ID if created."""

        if self.ticket is None:
            return None

        return self.ticket.id

    @property
    def ticket_no(self) -> str | None:
        """Return ticket number if created."""

        if self.ticket is None:
            return None

        return self.ticket.ticket_no

    def to_response_payload(self) -> dict[str, object]:
        """Return serializable result payload."""

        return {
            "created": self.created,
            "ticket_id": self.ticket_id,
            "ticket_no": self.ticket_no,
            "ticket": self.ticket.to_dict() if self.ticket is not None else None,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class HandoffTicketService:
    """Create handoff tickets from unified agent payloads."""

    def __init__(
        self,
        *,
        repository: HandoffTicketRepository,
    ) -> None:
        """Initialize service."""

        self._repository = repository

    def create_from_unified_result(
        self,
        *,
        user_text: str,
        unified_payload: dict[str, object],
        source_channel: str = "local_test",
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> HandoffTicketResult:
        """Create one handoff ticket from a unified agent response."""

        if unified_payload.get("handoff_required") is not True:
            return HandoffTicketResult(
                created=False,
                ticket=None,
                warnings=["handoff_required is false; ticket was not created"],
                errors=[],
            )

        selected_module = self._optional_text(
            unified_payload.get("selected_module"),
        )
        route_status = self._optional_text(
            unified_payload.get("route_status"),
        )
        parse_status = self._optional_text(
            unified_payload.get("parse_status"),
        )
        handler_status = self._optional_text(
            unified_payload.get("handler_status"),
        )

        ticket = self._repository.create(
            HandoffTicketCreate(
                ticket_no=self._generate_ticket_no(),
                user_text=user_text,
                source_channel=source_channel,
                session_id=session_id,
                user_id=user_id,
                selected_module=selected_module,
                route_status=route_status,
                route_confidence=self._optional_float(
                    unified_payload.get("route_confidence"),
                ),
                candidate_modules=self._list_of_text(
                    unified_payload.get("candidate_modules"),
                ),
                matched_signals=self._list_of_text(
                    unified_payload.get("matched_signals"),
                ),
                parse_status=parse_status,
                handler_status=handler_status,
                handoff_reason=self._build_handoff_reason(
                    selected_module=selected_module,
                    route_status=route_status,
                    handler_status=handler_status,
                ),
                answer_text=self._optional_text(
                    unified_payload.get("answer_text"),
                ),
                source_references=self._list_of_dict(
                    unified_payload.get("source_references"),
                ),
                module_payload=self._optional_dict(
                    unified_payload.get("module_payload"),
                ),
                risk_reasons=self._build_risk_reasons(
                    selected_module=selected_module,
                    route_status=route_status,
                    handler_status=handler_status,
                    unified_payload=unified_payload,
                ),
            )
        )

        return HandoffTicketResult(
            created=True,
            ticket=ticket,
            warnings=[],
            errors=[],
        )

    @staticmethod
    def _generate_ticket_no() -> str:
        """Generate a unique-looking handoff ticket number."""

        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        random_part = uuid4().hex[:8].upper()

        return f"HT-{date_part}-{random_part}"

    @staticmethod
    def _build_handoff_reason(
        *,
        selected_module: str | None,
        route_status: str | None,
        handler_status: str | None,
    ) -> str:
        """Build deterministic handoff reason."""

        if route_status == "ambiguous":
            return "当前问题包含多个业务意图，需拆分或由人工确认。"

        if route_status == "unknown":
            return "当前问题无法自动识别为受支持业务问题，需人工确认。"

        if selected_module == "price":
            return "当前系统未接入正式价格表，不能自动报价，需人工确认。"

        if selected_module == "logistics":
            return "该物流问题涉及运费、包邮、到货时间、承运商或加急承诺，需人工确认。"

        if selected_module == "quality":
            return "该质量问题涉及质量表现、售后责任、质保、退换或赔付，需人工确认。"

        if handler_status == "handoff":
            return "当前问题需要人工进一步确认。"

        return "当前问题需要人工进一步确认。"

    def _build_risk_reasons(
        self,
        *,
        selected_module: str | None,
        route_status: str | None,
        handler_status: str | None,
        unified_payload: dict[str, object],
    ) -> list[str]:
        """Build deterministic risk reason list."""

        existing_risk_reasons = self._list_of_text(
            unified_payload.get("risk_reasons"),
        )

        if existing_risk_reasons:
            return existing_risk_reasons

        if route_status == "ambiguous":
            return ["ambiguous_business_intent"]

        if route_status == "unknown":
            return ["unknown_business_intent"]

        if selected_module == "price":
            return ["price_without_price_table"]

        if selected_module == "logistics":
            return ["logistics_commitment_required"]

        if selected_module == "quality":
            return ["quality_commitment_required"]

        if handler_status == "handoff":
            return ["manual_handoff_required"]

        return ["manual_handoff_required"]

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

        if isinstance(value, int | float):
            return float(value)

        return float(str(value))

    @staticmethod
    def _list_of_text(value: object) -> list[str]:
        """Return list[str] from unknown value."""

        if not isinstance(value, list):
            return []

        return [str(item) for item in value]

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