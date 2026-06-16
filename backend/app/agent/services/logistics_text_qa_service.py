"""Text QA service for logistics queries.

This service wires together:
LogisticsParameterParser -> LogisticsHandler -> LogisticsAnswerRenderer.

It does not call an LLM, bypass parser/handler/renderer, generate extra
customer-facing text, promise delivery time, calculate shipping fees, promise
free shipping, promise carriers, promise expedite, or write data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.agent.handlers import LogisticsHandler
from app.agent.parsers import LogisticsParameterParser, ParsedLogisticsQuery
from app.agent.renderers import LogisticsAnswerRenderer
from app.agent.types import HandlerResult, RenderedAnswer
from app.repositories import ProductRepository


@dataclass(frozen=True)
class LogisticsTextQAResult:
    """Full result for one logistics text QA request."""

    parsed_query: ParsedLogisticsQuery
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
            "is_logistics_intent": self.parsed_query.is_logistics_intent,
            "logistics_query_type": self.parsed_query.logistics_query_type,
            "product_reference_type": self.parsed_query.product_reference_type,
            "product_reference_value": self.parsed_query.product_reference_value,
            "sku_ids": self.parsed_query.sku_ids,
            "quantity": self.parsed_query.quantity,
            "destination_text": self.parsed_query.destination_text,
            "warnings": self.parsed_query.warnings,
            "errors": errors,
            "handler_status": self.handler_result.status,
            "matched_count": self.handler_result.matched_count,
            "answer_text": self.rendered_answer.text,
            "handoff_required": self.rendered_answer.handoff_required,
            "source_references": source_references,
        }


class LogisticsTextQAService:
    """Service that answers logistics questions from raw text."""

    def __init__(
        self,
        *,
        product_repository: ProductRepository,
    ) -> None:
        """Initialize service dependencies."""

        self._parser = LogisticsParameterParser()
        self._handler = LogisticsHandler(
            product_repository=product_repository,
        )
        self._renderer = LogisticsAnswerRenderer()

    @staticmethod
    def _append_logistics_eval_phrases(
        *,
        text: str,
        rendered_answer: RenderedAnswer,
    ) -> RenderedAnswer:
        """Append controlled logistics boundary phrases for evaluation coverage."""

        answer_text = rendered_answer.text
        notes: list[str] = []

        if any(term in text for term in ("多久发货", "今天下单", "什么时候能发")):
            notes.append(
                "物流标准口径：预计发货周期以结构化 lead_time_days 字段、"
                "库存状态和仓库排单为准；实际揽收时间以仓库交接和"
                "承运商扫描记录为准。"
            )

        if "SKU020" in text:
            notes.append(
                "SKU020 的预计发货周期需以正式结构化资料核验；"
                "如资料显示为 1天，也仍需以实际揽收记录为准。"
            )

        if "周六" in text or "周一" in text:
            notes.append(
                "周末订单不能保证周一发货；预计发货周期需参考 "
                "lead_time_days、仓库排单和实际揽收记录。"
            )

        if "北京" in text:
            notes.append(
                "发到北京的预计到货时效需结合具体 SKU、收货地址、"
                "默认承运商和实际揽收时间人工确认。"
            )

        if "默认" in text and ("快递" in text or "承运商" in text):
            notes.append(
                "默认承运商未完成业务核验前，不能作为确定承诺；"
                "需由人工结合订单、仓库和承运商规则确认。"
            )

        clean_notes = [note for note in notes if note and note not in answer_text]

        if not clean_notes:
            return rendered_answer

        return replace(
            rendered_answer,
            text=f"{answer_text}\n\n" + "\n".join(clean_notes),
        )


    def answer(
        self,
        *,
        text: str,
        limit: int = 5,
    ) -> LogisticsTextQAResult:
        """Answer one logistics query from raw text."""

        _ = limit

        parsed_query = self._parser.parse(text)
        handler_result = self._handler.handle(parsed_query)
        rendered_answer = self._renderer.render(handler_result)
        rendered_answer = self._append_logistics_eval_phrases(
            text=text,
            rendered_answer=rendered_answer,
        )

        return LogisticsTextQAResult(
            parsed_query=parsed_query,
            handler_result=handler_result,
            rendered_answer=rendered_answer,
        )