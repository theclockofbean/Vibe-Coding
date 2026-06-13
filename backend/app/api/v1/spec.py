"""Specification query API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.handlers import SpecHandler
from app.agent.parsers import SpecParameterParser
from app.agent.renderers import SpecAnswerRenderer
from app.agent.services import SpecTextQAService
from app.core.database import get_db_session
from app.repositories import ProductRepository
from app.services import SpecQueryService

router = APIRouter(
    prefix="/spec",
    tags=["spec"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db_session),
]


class SpecQueryRequest(BaseModel):
    """Request body for a local specification query."""

    text: str = Field(
        min_length=1,
        max_length=500,
        description="Customer text to parse and answer.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum products returned for list queries.",
    )


class SpecQueryResponse(BaseModel):
    """Response body for a local specification query."""

    parse_status: str
    query_type: str | None
    query_value: str | None
    sku_ids: list[str]
    warnings: list[str]
    errors: list[str]
    answer_text: str
    handoff_required: bool
    source_references: list[dict[str, str]]


def build_spec_text_qa_service(session: Session) -> SpecTextQAService:
    """Build specification text QA service for one request."""

    repository = ProductRepository(session)
    spec_query_service = SpecQueryService(repository)
    handler = SpecHandler(spec_query_service)

    return SpecTextQAService(
        parser=SpecParameterParser(),
        handler=handler,
        renderer=SpecAnswerRenderer(),
    )


@router.post(
    "/query",
    response_model=SpecQueryResponse,
)
def query_spec(
    request: SpecQueryRequest,
    session: DatabaseSession,
) -> SpecQueryResponse:
    """Parse customer text and return a controlled specification answer."""

    text_qa_service = build_spec_text_qa_service(session)
    result = text_qa_service.answer(
        text=request.text,
        limit=request.limit,
    )

    return SpecQueryResponse(
        parse_status=result.parsed_query.status,
        query_type=result.parsed_query.query_type,
        query_value=result.parsed_query.query_value,
        sku_ids=result.parsed_query.sku_ids,
        warnings=result.parsed_query.warnings,
        errors=result.parsed_query.errors,
        answer_text=result.rendered_answer.text,
        handoff_required=result.rendered_answer.handoff_required,
        source_references=result.rendered_answer.source_references,
    )