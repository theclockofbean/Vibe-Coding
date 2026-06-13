"""Quality query API.

This route wires HTTP requests to QualityTextQAService.

It does not call an LLM, bypass parser/handler/renderer, generate extra
customer-facing text, promise durability, promise rust resistance, promise
scratch resistance, promise warranty, promise returns/exchanges, promise
compensation, judge quality responsibility, or write data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.services import QualityTextQAService
from app.core.database import get_session_factory
from app.repositories import ProductRepository

router = APIRouter()


class QualityQueryRequest(BaseModel):
    """Quality query request body."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User quality query text.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Reserved limit for future multi-product rendering.",
    )


@router.post("/query")
def query_quality(request: QualityQueryRequest) -> dict[str, Any]:
    """Query quality answer by raw text."""

    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="text must not be blank",
        )

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        service = QualityTextQAService(
            product_repository=product_repository,
        )
        result = service.answer(
            text=text,
            limit=request.limit,
        )

    return result.to_response_payload()