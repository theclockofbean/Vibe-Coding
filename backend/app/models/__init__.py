"""SQLAlchemy ORM model registry.

Importing this package registers every ORM table in ``Base.metadata``.
Alembic and database initialization code should import models from here
instead of importing individual model modules separately.
"""

from app.models.base import NAMING_CONVENTION, Base, TimestampMixin
from app.models.conversation import ConversationMessage, ConversationSession
from app.models.evaluation import (
    EvaluationCase,
    EvaluationResult,
    EvaluationRun,
)
from app.models.import_batch import DataImportBatch
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.product import Product

__all__ = [
    "Base",
    "ConversationMessage",
    "ConversationSession",
    "DataImportBatch",
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationRun",
    "KnowledgeChunk",
    "NAMING_CONVENTION",
    "Product",
    "TimestampMixin",
]