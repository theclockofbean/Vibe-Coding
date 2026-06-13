"""Unified text QA service.

This service routes a raw user query to exactly one Phase 1 module and wraps
the module result into a unified response.

It does not call an LLM, directly query business tables, bypass module
TextQAService objects, generate business commitments, or merge multiple module
answers.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.handlers import PriceHandler, SpecHandler
from app.agent.parsers import PriceParameterParser, SpecParameterParser
from app.agent.renderers import PriceAnswerRenderer, SpecAnswerRenderer
from app.agent.routers import (
    UnifiedIntentResult,
    UnifiedIntentRouter,
    UnifiedModule,
)
from app.agent.services.logistics_text_qa_service import LogisticsTextQAService
from app.agent.services.price_text_qa_service import PriceTextQAService
from app.agent.services.quality_text_qa_service import QualityTextQAService
from app.agent.services.spec_text_qa_service import SpecTextQAService
from app.repositories import ProductRepository
from app.services import SpecQueryService


@dataclass(frozen=True)
class UnifiedTextQAResult:
    """Unified result for one text QA request."""

    route_result: UnifiedIntentResult
    selected_module: UnifiedModule | None
    route_status: str
    parse_status: str
    handler_status: str
    answer_text: str
    handoff_required: bool
    source_references: list[dict[str, object]]
    module_payload: dict[str, object] | None
    warnings: list[str]
    errors: list[str]

    def to_response_payload(self) -> dict[str, object]:
        """Return API-ready response payload."""

        return {
            "selected_module": self.selected_module,
            "route_status": self.route_status,
            "route_confidence": self.route_result.confidence,
            "candidate_modules": self.route_result.candidate_modules,
            "matched_signals": self.route_result.matched_signals,
            "parse_status": self.parse_status,
            "handler_status": self.handler_status,
            "answer_text": self.answer_text,
            "handoff_required": self.handoff_required,
            "source_references": self.source_references,
            "module_payload": self.module_payload,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class UnifiedTextQAService:
    """Route text to one Phase 1 QA service and return unified result."""

    def __init__(
        self,
        *,
        product_repository: ProductRepository,
        intent_router: UnifiedIntentRouter | None = None,
    ) -> None:
        """Initialize service dependencies."""

        self._product_repository = product_repository
        self._intent_router = intent_router or UnifiedIntentRouter()

        self._spec_service = self._build_spec_service(product_repository)
        self._price_service = self._build_price_service()
        self._logistics_service = LogisticsTextQAService(
            product_repository=product_repository,
        )
        self._quality_service = QualityTextQAService(
            product_repository=product_repository,
        )

    def answer(
        self,
        *,
        text: str,
        limit: int = 5,
    ) -> UnifiedTextQAResult:
        """Answer one raw query through the unified routing layer."""

        route_result = self._intent_router.route(text)

        if route_result.status != "routed" or route_result.selected_module is None:
            return self._route_controlled_result(route_result)

        selected_module = route_result.selected_module

        if selected_module == "spec":
            module_payload = self._answer_spec(text=text, limit=limit)
            return self._from_module_payload(
                route_result=route_result,
                module_payload=module_payload,
                selected_module="spec",
                default_handler_status=self._handler_status_from_handoff(
                    module_payload,
                ),
            )

        if selected_module == "price":
            module_payload = self._answer_price(text=text)
            return self._from_module_payload(
                route_result=route_result,
                module_payload=module_payload,
                selected_module="price",
                default_handler_status="invalid_request",
            )

        if selected_module == "logistics":
            module_payload = self._answer_logistics(text=text, limit=limit)
            return self._from_module_payload(
                route_result=route_result,
                module_payload=module_payload,
                selected_module="logistics",
                default_handler_status="invalid_request",
            )

        if selected_module == "quality":
            module_payload = self._answer_quality(text=text, limit=limit)
            return self._from_module_payload(
                route_result=route_result,
                module_payload=module_payload,
                selected_module="quality",
                default_handler_status="invalid_request",
            )

        return self._route_controlled_result(route_result)

    @staticmethod
    def _build_spec_service(
        product_repository: ProductRepository,
    ) -> SpecTextQAService:
        """Build spec text QA service."""

        spec_query_service = SpecQueryService(product_repository)
        handler = SpecHandler(spec_query_service)

        return SpecTextQAService(
            parser=SpecParameterParser(),
            handler=handler,
            renderer=SpecAnswerRenderer(),
        )

    @staticmethod
    def _build_price_service() -> PriceTextQAService:
        """Build price text QA service."""

        return PriceTextQAService(
            parser=PriceParameterParser(),
            handler=PriceHandler(),
            renderer=PriceAnswerRenderer(),
        )

    def _answer_spec(
        self,
        *,
        text: str,
        limit: int,
    ) -> dict[str, object]:
        """Answer through SpecTextQAService and return module payload."""

        result = self._spec_service.answer(
            text=text,
            limit=limit,
        )

        return {
            "parse_status": result.parsed_query.status,
            "query_type": result.parsed_query.query_type,
            "query_value": result.parsed_query.query_value,
            "sku_ids": result.parsed_query.sku_ids,
            "warnings": result.parsed_query.warnings,
            "errors": result.parsed_query.errors,
            "answer_text": result.rendered_answer.text,
            "handoff_required": result.rendered_answer.handoff_required,
            "source_references": self._serialize_source_references(
                result.rendered_answer.source_references,
            ),
        }

    def _answer_price(
        self,
        *,
        text: str,
    ) -> dict[str, object]:
        """Answer through PriceTextQAService and return module payload."""

        result = self._price_service.answer(text=text)

        return {
            "parse_status": result.parsed_query.status,
            "is_price_intent": result.parsed_query.is_price_intent,
            "price_query_type": result.parsed_query.price_query_type,
            "product_reference_type": result.parsed_query.product_reference_type,
            "product_reference_value": result.parsed_query.product_reference_value,
            "sku_ids": result.parsed_query.sku_ids,
            "quantity": result.parsed_query.quantity,
            "warnings": result.parsed_query.warnings,
            "errors": result.parsed_query.errors,
            "handler_status": result.handler_result.status,
            "answer_text": result.rendered_answer.text,
            "handoff_required": result.rendered_answer.handoff_required,
            "source_references": self._serialize_source_references(
                result.rendered_answer.source_references,
            ),
        }

    def _answer_logistics(
        self,
        *,
        text: str,
        limit: int,
    ) -> dict[str, object]:
        """Answer through LogisticsTextQAService and return module payload."""

        result = self._logistics_service.answer(
            text=text,
            limit=limit,
        )

        return result.to_response_payload()

    def _answer_quality(
        self,
        *,
        text: str,
        limit: int,
    ) -> dict[str, object]:
        """Answer through QualityTextQAService and return module payload."""

        result = self._quality_service.answer(
            text=text,
            limit=limit,
        )

        return result.to_response_payload()

    def _from_module_payload(
        self,
        *,
        route_result: UnifiedIntentResult,
        module_payload: dict[str, object],
        selected_module: UnifiedModule,
        default_handler_status: str,
    ) -> UnifiedTextQAResult:
        """Build unified result from one module payload."""

        parse_status = self._get_text_value(
            module_payload,
            "parse_status",
            default=route_result.status,
        )
        handler_status = self._get_text_value(
            module_payload,
            "handler_status",
            default=default_handler_status,
        )
        answer_text = self._get_text_value(
            module_payload,
            "answer_text",
            default="当前问题已进入对应模块处理，但未生成可展示回答。",
        )
        handoff_required = self._get_bool_value(
            module_payload,
            "handoff_required",
            default=False,
        )
        source_references = self._get_source_references(module_payload)

        return UnifiedTextQAResult(
            route_result=route_result,
            selected_module=selected_module,
            route_status=route_result.status,
            parse_status=parse_status,
            handler_status=handler_status,
            answer_text=answer_text,
            handoff_required=handoff_required,
            source_references=source_references,
            module_payload=module_payload,
            warnings=self._get_list_of_text(module_payload, "warnings")
            + route_result.warnings,
            errors=self._get_list_of_text(module_payload, "errors")
            + route_result.errors,
        )

    @staticmethod
    def _route_controlled_result(
        route_result: UnifiedIntentResult,
    ) -> UnifiedTextQAResult:
        """Return controlled result when no module should be called."""

        if route_result.status == "ambiguous":
            answer_text = (
                "识别到多个业务问题："
                f"{'、'.join(route_result.candidate_modules)}。"
                "当前统一入口 v0.1 不自动合并多个模块回答，"
                "请拆分为规格、价格、物流或质量中的一个问题后重新提问。"
            )
        elif route_result.status == "unknown":
            answer_text = (
                "当前未识别到可处理的业务问题，请补充 SKU 和具体问题，"
                "例如规格、价格、发货或质量。"
            )
        else:
            answer_text = "请求内容无效，请输入 1 到 500 字符的问题。"

        return UnifiedTextQAResult(
            route_result=route_result,
            selected_module=None,
            route_status=route_result.status,
            parse_status=route_result.status,
            handler_status="invalid_request",
            answer_text=answer_text,
            handoff_required=False,
            source_references=[],
            module_payload=None,
            warnings=route_result.warnings,
            errors=route_result.errors,
        )

    @staticmethod
    def _handler_status_from_handoff(
        module_payload: dict[str, object],
    ) -> str:
        """Map legacy spec payload to a handler status."""

        handoff_required = module_payload.get("handoff_required")

        if handoff_required is True:
            return "handoff"

        return "success"

    @staticmethod
    def _get_text_value(
        payload: dict[str, object],
        key: str,
        *,
        default: str,
    ) -> str:
        """Read text value from payload."""

        value = payload.get(key)

        if value is None:
            return default

        return str(value)

    @staticmethod
    def _get_bool_value(
        payload: dict[str, object],
        key: str,
        *,
        default: bool,
    ) -> bool:
        """Read bool value from payload."""

        value = payload.get(key)

        if isinstance(value, bool):
            return value

        return default

    @staticmethod
    def _get_list_of_text(
        payload: dict[str, object],
        key: str,
    ) -> list[str]:
        """Read list[str] value from payload."""

        value = payload.get(key)

        if not isinstance(value, list):
            return []

        return [str(item) for item in value]

    def _get_source_references(
        self,
        payload: dict[str, object],
    ) -> list[dict[str, object]]:
        """Read source references from payload."""

        return self._serialize_source_references(
            payload.get("source_references", []),
        )

    @staticmethod
    def _serialize_source_references(
        source_references: object,
    ) -> list[dict[str, object]]:
        """Serialize source references into plain dictionaries."""

        if not isinstance(source_references, list):
            return []

        serialized: list[dict[str, object]] = []

        for reference in source_references:
            serialized_reference = (
                UnifiedTextQAService._serialize_source_reference(reference)
            )

            if serialized_reference:
                serialized.append(serialized_reference)

        return serialized

    @staticmethod
    def _serialize_source_reference(
        reference: object,
    ) -> dict[str, object]:
        """Serialize one source reference into a plain dictionary."""

        if isinstance(reference, dict):
            return {
                str(key): value
                for key, value in reference.items()
            }

        to_dict = getattr(reference, "to_dict", None)

        if callable(to_dict):
            value = to_dict()

            if isinstance(value, dict):
                return {
                    str(key): item
                    for key, item in value.items()
                }

        result: dict[str, object] = {}

        for key in (
            "source_type",
            "source_name",
            "reference_id",
            "source_table",
            "query_type",
            "query_value",
        ):
            value = getattr(reference, key, None)

            if value is not None:
                result[key] = value

        return result