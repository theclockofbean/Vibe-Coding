"""Price intent handler.

This handler receives ParsedPriceQuery and converts it into a unified
HandlerResult.

It does not query the database, call an LLM, or generate prices.
"""

from __future__ import annotations

from typing import TypeAlias

from app.agent.parsers import ParsedPriceQuery
from app.agent.types import HandlerResult, HandlerStatus

PriceHandlerResult: TypeAlias = HandlerResult


class PriceHandler:
    """Handle structured price queries without generating quotes."""

    handler_name = "price_handler"
    primary_intent = "price"

    def handle(self, parsed_query: ParsedPriceQuery) -> HandlerResult:
        """Handle one parsed price query."""

        if parsed_query.status == "parsed":
            return self._handoff_result(parsed_query)

        if parsed_query.status == "missing_product_reference":
            return self._missing_reference_result(parsed_query)

        if parsed_query.status == "ambiguous":
            return self._invalid_request_result(
                parsed_query,
                status="invalid_request",
            )

        if parsed_query.status == "not_price_intent":
            return self._invalid_request_result(
                parsed_query,
                status="invalid_request",
            )

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="failed",
            matched_count=0,
            handoff_required=True,
            facts=None,
            errors=["unsupported price parse status"],
            source_references=[],
        )

    def _handoff_result(
        self,
        parsed_query: ParsedPriceQuery,
    ) -> HandlerResult:
        """Return handoff result for parsed price query."""

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="handoff",
            matched_count=1,
            handoff_required=True,
            facts=self._build_facts(parsed_query),
            errors=[],
            source_references=[],
        )

    def _missing_reference_result(
        self,
        parsed_query: ParsedPriceQuery,
    ) -> HandlerResult:
        """Return handoff result when price intent lacks product reference."""

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="handoff",
            matched_count=0,
            handoff_required=True,
            facts=self._build_facts(parsed_query),
            errors=parsed_query.errors,
            source_references=[],
        )

    def _invalid_request_result(
        self,
        parsed_query: ParsedPriceQuery,
        *,
        status: HandlerStatus,
    ) -> HandlerResult:
        """Return invalid request result for unsupported parser states."""

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status=status,
            matched_count=0,
            handoff_required=False,
            facts=self._build_facts(parsed_query),
            errors=parsed_query.errors,
            source_references=[],
        )

    @staticmethod
    def _build_facts(
        parsed_query: ParsedPriceQuery,
    ) -> dict[str, object]:
        """Build price handler facts without price values."""

        return {
            "raw_text": parsed_query.raw_text,
            "is_price_intent": parsed_query.is_price_intent,
            "price_query_type": parsed_query.price_query_type,
            "product_reference_type": parsed_query.product_reference_type,
            "product_reference_value": parsed_query.product_reference_value,
            "sku_ids": parsed_query.sku_ids,
            "quantity": parsed_query.quantity,
            "pricing_available": False,
            "requires_human_quote": True,
            "reason": "formal price table is not connected",
        }