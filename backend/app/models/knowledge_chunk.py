"""Knowledge chunk ORM model.

The knowledge_chunks table stores source text, provenance, review state, and
the logical relationship between PostgreSQL records and Qdrant points. Vector
values are never stored in PostgreSQL.
"""

from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

KNOWLEDGE_TYPES: Final[tuple[str, ...]] = (
    "quality",
    "logistics",
)

KNOWLEDGE_VERIFICATION_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "verified",
    "rejected",
)


def _as_sql_values(values: tuple[str, ...]) -> str:
    """Convert trusted constant values into a SQL CHECK value list."""

    return ", ".join(f"'{value}'" for value in values)


class KnowledgeChunk(TimestampMixin, Base):
    """Store metadata and source text for one knowledge-base chunk."""

    __tablename__ = "knowledge_chunks"

    __table_args__ = (
        CheckConstraint(
            f"knowledge_type IN ({_as_sql_values(KNOWLEDGE_TYPES)})",
            name="knowledge_type_allowed",
        ),
        CheckConstraint(
            (
                "verification_status IN "
                f"({_as_sql_values(KNOWLEDGE_VERIFICATION_STATUSES)})"
            ),
            name="verification_status_allowed",
        ),
        CheckConstraint(
            "btrim(collection_name) <> ''",
            name="collection_name_not_blank",
        ),
        CheckConstraint(
            "btrim(source_file) <> ''",
            name="source_file_not_blank",
        ),
        CheckConstraint(
            "btrim(chunk_text) <> ''",
            name="chunk_text_not_blank",
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9A-Fa-f]{64}$'",
            name="content_hash_sha256_format",
        ),
        CheckConstraint(
            "verification_status <> 'rejected' OR is_active = false",
            name="rejected_chunk_inactive",
        ),
        UniqueConstraint(
            "chunk_id",
            name="uq_knowledge_chunks_chunk_id",
        ),
        UniqueConstraint(
            "collection_name",
            "qdrant_point_id",
            name="uq_knowledge_chunks_collection_qdrant_point",
        ),
        Index(
            "ix_knowledge_chunks_knowledge_type",
            "knowledge_type",
        ),
        Index(
            "ix_knowledge_chunks_verification_status",
            "verification_status",
        ),
        Index(
            "ix_knowledge_chunks_is_active",
            "is_active",
        ),
        Index(
            "ix_knowledge_chunks_content_hash",
            "content_hash",
        ),
        Index(
            "ix_knowledge_chunks_source_record_id",
            "source_record_id",
        ),
        Index(
            "ix_knowledge_chunks_import_batch_id",
            "import_batch_id",
        ),
        Index(
            "ix_knowledge_chunks_type_status_active",
            "knowledge_type",
            "verification_status",
            "is_active",
        ),
        Index(
            "ix_knowledge_chunks_metadata_gin",
            "metadata",
            postgresql_using="gin",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    chunk_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        default=uuid4,
    )

    knowledge_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    collection_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_record_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    source_version: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
    )

    qdrant_point_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    verification_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    import_batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "data_import_batches.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    # "metadata" is reserved by SQLAlchemy DeclarativeBase, so the Python
    # attribute is named metadata_ while the PostgreSQL column remains metadata.
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


__all__ = [
    "KNOWLEDGE_TYPES",
    "KNOWLEDGE_VERIFICATION_STATUSES",
    "KnowledgeChunk",
]