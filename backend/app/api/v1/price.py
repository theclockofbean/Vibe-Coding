"""Controlled price query API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.handlers import PriceHandler
from app.agent.parsers import PriceParameterParser
from app.agent.renderers import PriceAnswerRenderer
from app.agent.services import PriceTextQAService

router = APIRouter(
    prefix="/price",
    tags=["price"],
)


class PriceQueryRequest(BaseModel):
    """Request body for a controlled price query."""

    text: str = Field(
        min_length=1,
        max_length=500,
        description="Customer text to parse and answer.",
    )


class PriceQueryResponse(BaseModel):
    """Response body for a controlled price query."""

    parse_status: str
    is_price_intent: bool
    price_query_type: str | None
    product_reference_type: str | None
    product_reference_value: str | None
    sku_ids: list[str]
    quantity: int | None
    warnings: list[str]
    errors: list[str]
    handler_status: str
    answer_text: str
    handoff_required: bool
    source_references: list[dict[str, str]]


def build_price_text_qa_service() -> PriceTextQAService:
    """Build controlled price text QA service."""

    return PriceTextQAService(
        parser=PriceParameterParser(),
        handler=PriceHandler(),
        renderer=PriceAnswerRenderer(),
    )


@router.post(
    "/query",
    response_model=PriceQueryResponse,
)
def query_price(request: PriceQueryRequest) -> PriceQueryResponse:
    """Parse customer text and return a controlled price answer."""

    service = build_price_text_qa_service()
    result = service.answer(text=request.text)

    return PriceQueryResponse(
        parse_status=result.parsed_query.status,
        is_price_intent=result.parsed_query.is_price_intent,
        price_query_type=result.parsed_query.price_query_type,
        product_reference_type=result.parsed_query.product_reference_type,
        product_reference_value=result.parsed_query.product_reference_value,
        sku_ids=result.parsed_query.sku_ids,
        quantity=result.parsed_query.quantity,
        warnings=result.parsed_query.warnings,
        errors=result.parsed_query.errors,
        handler_status=result.handler_result.status,
        answer_text=result.rendered_answer.text,
        handoff_required=result.rendered_answer.handoff_required,
        source_references=result.rendered_answer.source_references,
    )