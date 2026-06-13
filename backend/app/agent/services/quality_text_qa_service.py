"""Text QA service for quality queries.

This service wires together:
QualityParameterParser -> QualityHandler -> QualityAnswerRenderer.

It does not call an LLM, bypass parser/handler/renderer, generate extra
customer-facing text, promise durability, promise rust resistance, promise
scratch resistance, promise warranty, promise returns/exchanges, promise
compensation, judge quality responsibility, or write data.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.handlers import QualityHandler
from app.agent.parsers import ParsedQualityQuery, QualityParameterParser
from app.agent.renderers import QualityAnswerRenderer
from app.agent.types import HandlerResult, RenderedAnswer
from app.repositories import ProductRepository


@dataclass(frozen=True)
class QualityTextQAResult:
    """Full result for one quality text QA request."""

    parsed_query: ParsedQualityQuery
    handler_result: HandlerResult
    rendered_answer: RenderedAnswer

    def to_response_payload(self) -> dict[str, object]:
        """Return API-ready response payload."""

        handler_payload = self.handler_result.to_dict()
        source_references = handler_payload.get("source_references", [])

        if not isinstance(source_references, list):
            source_references = []

        errors = (
            self.handler_result.errors
            if self.handler_result.errors
            else self.parsed_query.errors
        )

        return {
            "parse_status": self.parsed_query.status,
            "is_quality_intent": self.parsed_query.is_quality_intent,
            "quality_query_type": self.parsed_query.quality_query_type,
            "product_reference_type": self.parsed_query.product_reference_type,
            "product_reference_value": self.parsed_query.product_reference_value,
            "sku_ids": self.parsed_query.sku_ids,
            "oem_reference_numbers": self.parsed_query.oem_reference_numbers,
            "thread_specs": self.parsed_query.thread_specs,
            "warnings": self.parsed_query.warnings,
            "errors": errors,
            "handler_status": self.handler_result.status,
            "matched_count": self.handler_result.matched_count,
            "answer_text": self.rendered_answer.text,
            "handoff_required": self.rendered_answer.handoff_required,
            "source_references": source_references,
        }


class QualityTextQAService:
    """Service that answers quality questions from raw text."""

    def __init__(
        self,
        *,
        product_repository: ProductRepository,
    ) -> None:
        """Initialize service dependencies."""

        self._parser = QualityParameterParser()
        self._handler = QualityHandler(
            product_repository=product_repository,
        )
        self._renderer = QualityAnswerRenderer()

    def answer(
        self,
        *,
        text: str,
        limit: int = 5,
    ) -> QualityTextQAResult:
        """Answer one quality query from raw text."""

        _ = limit

        parsed_query = self._parser.parse(text)
        handler_result = self._handler.handle(parsed_query)
        rendered_answer = self._renderer.render(handler_result)

        return QualityTextQAResult(
            parsed_query=parsed_query,
            handler_result=handler_result,
            rendered_answer=rendered_answer,
        )