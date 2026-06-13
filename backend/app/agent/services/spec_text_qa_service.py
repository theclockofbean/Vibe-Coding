"""Text QA service for specification queries.

This service centralizes the flow:
customer text -> parser -> handler -> renderer.

It does not call an LLM and does not write database data.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.handlers import SpecHandler
from app.agent.parsers import ParsedSpecQuery, SpecParameterParser
from app.agent.renderers import SpecAnswerRenderer
from app.agent.types import HandlerResult, RenderedAnswer


@dataclass(frozen=True)
class TextQAResult:
    """Result returned by a text QA service."""

    parsed_query: ParsedSpecQuery
    rendered_answer: RenderedAnswer
    handler_result: HandlerResult | None = None

    def to_response_payload(self) -> dict[str, object]:
        """Return a JSON-serializable API-style payload."""

        return {
            "parse_status": self.parsed_query.status,
            "query_type": self.parsed_query.query_type,
            "query_value": self.parsed_query.query_value,
            "sku_ids": self.parsed_query.sku_ids,
            "warnings": self.parsed_query.warnings,
            "errors": self.parsed_query.errors,
            "answer_text": self.rendered_answer.text,
            "handoff_required": self.rendered_answer.handoff_required,
            "source_references": self.rendered_answer.source_references,
        }


class SpecTextQAService:
    """Run the full local text QA flow for specification queries."""

    def __init__(
        self,
        *,
        parser: SpecParameterParser,
        handler: SpecHandler,
        renderer: SpecAnswerRenderer,
    ) -> None:
        """Initialize the service with parser, handler, and renderer."""

        self._parser = parser
        self._handler = handler
        self._renderer = renderer

    def answer(
        self,
        *,
        text: str,
        limit: int = 5,
    ) -> TextQAResult:
        """Answer one customer text with controlled specification logic."""

        parsed_query = self._parser.parse(text, limit=limit)

        if parsed_query.status != "parsed":
            rendered_answer = self.render_parse_failure(parsed_query)
            return TextQAResult(
                parsed_query=parsed_query,
                rendered_answer=rendered_answer,
                handler_result=None,
            )

        handler_input = parsed_query.to_handler_input()
        handler_result = self._handler.handle(handler_input)
        rendered_answer = self._renderer.render(handler_result)

        return TextQAResult(
            parsed_query=parsed_query,
            rendered_answer=rendered_answer,
            handler_result=handler_result,
        )

    @staticmethod
    def render_parse_failure(
        parsed_query: ParsedSpecQuery,
    ) -> RenderedAnswer:
        """Render parser failure without entering the handler."""

        if parsed_query.status == "ambiguous":
            return SpecTextQAService._render_ambiguous_query(parsed_query)

        error_text = "；".join(parsed_query.errors)

        if error_text:
            text = (
                "当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格。"
                f"未进入查询的原因：{error_text}。"
            )
        else:
            text = "当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格。"

        return RenderedAnswer(
            text=text,
            handoff_required=False,
            source_references=[],
        )

    @staticmethod
    def _render_ambiguous_query(
        parsed_query: ParsedSpecQuery,
    ) -> RenderedAnswer:
        """Render ambiguous parser result."""

        if "multiple OEM reference numbers found" in parsed_query.errors:
            text = "识别到多个 OEM 对照号，请一次只查询一个 OEM 对照号。"
        elif "multiple thread specs found" in parsed_query.errors:
            text = "识别到多个螺纹规格，请一次只查询一个螺纹规格。"
        else:
            text = "规格查询条件不唯一，请补充明确的 SKU、OEM 对照号或螺纹规格。"

        return RenderedAnswer(
            text=text,
            handoff_required=False,
            source_references=[],
        )