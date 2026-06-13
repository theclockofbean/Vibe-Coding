"""Text QA service for price queries.

This service centralizes the flow:
customer text -> price parser -> price handler -> price renderer.

It does not call an LLM, query the database, or generate prices.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.handlers import PriceHandler
from app.agent.parsers import ParsedPriceQuery, PriceParameterParser
from app.agent.renderers import PriceAnswerRenderer
from app.agent.types import HandlerResult, RenderedAnswer


@dataclass(frozen=True)
class PriceTextQAResult:
    """Result returned by price text QA service."""

    parsed_query: ParsedPriceQuery
    handler_result: HandlerResult
    rendered_answer: RenderedAnswer

    def to_response_payload(self) -> dict[str, object]:
        """Return a JSON-serializable API-style payload."""

        return {
            "parse_status": self.parsed_query.status,
            "is_price_intent": self.parsed_query.is_price_intent,
            "price_query_type": self.parsed_query.price_query_type,
            "product_reference_type": self.parsed_query.product_reference_type,
            "product_reference_value": self.parsed_query.product_reference_value,
            "sku_ids": self.parsed_query.sku_ids,
            "quantity": self.parsed_query.quantity,
            "warnings": self.parsed_query.warnings,
            "errors": self.parsed_query.errors,
            "handler_status": self.handler_result.status,
            "answer_text": self.rendered_answer.text,
            "handoff_required": self.rendered_answer.handoff_required,
            "source_references": self.rendered_answer.source_references,
        }


class PriceTextQAService:
    """Run the full local text QA flow for price queries."""

    def __init__(
        self,
        *,
        parser: PriceParameterParser,
        handler: PriceHandler,
        renderer: PriceAnswerRenderer,
    ) -> None:
        """Initialize the service with parser, handler, and renderer."""

        self._parser = parser
        self._handler = handler
        self._renderer = renderer

    def answer(self, *, text: str) -> PriceTextQAResult:
        """Answer one customer text with controlled price logic."""

        parsed_query = self._parser.parse(text)
        handler_result = self._handler.handle(parsed_query)
        rendered_answer = self._renderer.render(handler_result)

        return PriceTextQAResult(
            parsed_query=parsed_query,
            handler_result=handler_result,
            rendered_answer=rendered_answer,
        )