"""Logistics API endpoints.

This module exposes controlled logistics text QA.

It does not call an LLM, generate logistics commitments, calculate shipping
fees, promise free shipping, promise delivery time, promise carriers, promise
expedite, or write data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.services import LogisticsTextQAService
from app.core.database import get_db_session
from app.repositories import ProductRepository


router = APIRouter(
    prefix="/logistics",
    tags=["logistics"],
)


class LogisticsQueryRequest(BaseModel):
    """Request body for logistics query."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User logistics query text.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum result limit for future multi-product rendering.",
    )


class SourceReferenceResponse(BaseModel):
    """Source reference in logistics response."""

    source_type: str
    source_name: str
    reference_id: str


class LogisticsQueryResponse(BaseModel):
    """Response body for logistics query."""

    parse_status: str
    is_logistics_intent: bool
    logistics_query_type: str | None = None
    product_reference_type: str | None = None
    product_reference_value: str | None = None
    sku_ids: list[str] = Field(default_factory=list)
    quantity: int | None = None
    destination_text: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    handler_status: str
    matched_count: int
    answer_text: str
    handoff_required: bool
    source_references: list[SourceReferenceResponse] = Field(default_factory=list)


@router.post(
    "/query",
    response_model=LogisticsQueryResponse,
)
def query_logistics(
    request: LogisticsQueryRequest,
    db_session: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Answer a controlled logistics query."""

    product_repository = ProductRepository(db_session)
    service = LogisticsTextQAService(
        product_repository=product_repository,
    )

    result = service.answer(
        text=request.text,
        limit=request.limit,
    )

    return result.to_response_payload()