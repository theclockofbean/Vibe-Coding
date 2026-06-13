"""Service exports."""

from app.services.spec_query_service import (
    ProductSpecFact,
    SpecQueryResult,
    SpecQueryService,
)

__all__ = [
    "ProductSpecFact",
    "SpecQueryResult",
    "SpecQueryService",
]