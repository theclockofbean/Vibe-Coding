"""Specification intent handler.

This handler receives already-classified specification query parameters and
delegates product fact lookup to SpecQueryService.

It does not parse free-form customer text, call an LLM, or invent facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal, TypeAlias

from app.agent.types import HandlerResult, HandlerStatus
from app.services import SpecQueryResult, SpecQueryService

SpecQueryType = Literal[
    "sku_id",
    "sku_ids",
    "thread_spec",
    "thread_dimensions",
    "oem_reference_number",
]

SpecHandlerStatus: TypeAlias = HandlerStatus
SpecHandlerResult: TypeAlias = HandlerResult


@dataclass(frozen=True)
class SpecHandlerInput:
    """Normalized input for the specification handler.

    The intent classifier or upstream parser is responsible for filling these
    fields. This handler only validates the structured parameters.
    """

    query_type: SpecQueryType
    query_value: str | None = None
    sku_ids: list[str] = field(default_factory=list)
    diameter_mm: str | None = None
    pitch_mm: str | None = None
    limit: int = 20


class SpecHandler:
    """Handle structured specification queries."""

    handler_name = "spec_handler"
    primary_intent = "spec"

    def __init__(self, spec_query_service: SpecQueryService) -> None:
        """Initialize handler with SpecQueryService."""

        self._spec_query_service = spec_query_service

    def handle(self, handler_input: SpecHandlerInput) -> HandlerResult:
        """Handle one structured specification query."""

        try:
            query_result = self._query(handler_input)
        except ValueError as exc:
            return self._invalid_request(str(exc))

        status: HandlerStatus = (
            "success" if query_result.matched_count > 0 else "not_found"
        )

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status=status,
            matched_count=query_result.matched_count,
            handoff_required=query_result.handoff_required,
            facts=query_result.to_dict(),
            errors=[],
            source_references=self._build_source_references(query_result),
        )

    def _query(self, handler_input: SpecHandlerInput) -> SpecQueryResult:
        """Dispatch input to the corresponding query method."""

        if handler_input.limit <= 0:
            raise ValueError("limit must be positive")

        if handler_input.query_type == "sku_id":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_sku(query_value)

        if handler_input.query_type == "sku_ids":
            if not handler_input.sku_ids:
                raise ValueError("sku_ids must not be empty")

            return self._spec_query_service.query_by_sku_ids(
                handler_input.sku_ids
            )

        if handler_input.query_type == "thread_spec":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_thread_spec(
                query_value,
                limit=handler_input.limit,
            )

        if handler_input.query_type == "thread_dimensions":
            diameter_mm = self._parse_decimal(
                handler_input.diameter_mm,
                field_name="diameter_mm",
            )
            pitch_mm = self._parse_decimal(
                handler_input.pitch_mm,
                field_name="pitch_mm",
            )

            return self._spec_query_service.query_by_thread_dimensions(
                diameter_mm=diameter_mm,
                pitch_mm=pitch_mm,
                limit=handler_input.limit,
            )

        if handler_input.query_type == "oem_reference_number":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_oem_reference(query_value)

        raise ValueError(f"unsupported query_type: {handler_input.query_type}")

    @staticmethod
    def _require_query_value(handler_input: SpecHandlerInput) -> str:
        """Return non-blank query_value or raise ValueError."""

        if handler_input.query_value is None:
            raise ValueError("query_value is required")

        query_value = handler_input.query_value.strip()

        if not query_value:
            raise ValueError("query_value must not be blank")

        return query_value

    @staticmethod
    def _parse_decimal(
        value: str | None,
        *,
        field_name: str,
    ) -> Decimal:
        """Parse a positive decimal handler input field."""

        if value is None:
            raise ValueError(f"{field_name} is required")

        text_value = value.strip()

        try:
            decimal_value = Decimal(text_value)
        except InvalidOperation as exc:
            raise ValueError(
                f"{field_name} must be numeric, got {text_value!r}"
            ) from exc

        if decimal_value <= 0:
            raise ValueError(
                f"{field_name} must be positive, got {text_value!r}"
            )

        return decimal_value

    def _invalid_request(self, error: str) -> HandlerResult:
        """Return invalid request result."""

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="invalid_request",
            matched_count=0,
            handoff_required=False,
            facts=None,
            errors=[error],
            source_references=[],
        )

    @staticmethod
    def _build_source_references(
        query_result: SpecQueryResult,
    ) -> list[dict[str, str]]:
        """Build compact source references for downstream response rendering."""

        if query_result.matched_count == 0:
            return []

        return [
            {
                "source_table": query_result.source_table,
                "query_type": query_result.query_type,
                "query_value": query_result.query_value,
            }
        ]