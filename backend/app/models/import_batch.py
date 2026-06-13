"""Data import batch model."""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import CHAR, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

IMPORT_DATA_TYPES: Final[tuple[str, ...]] = (
    "sku_master",
    "evaluation_cases",
    "spec_questions",
    "quality_questions",
    "price_questions",
    "logistics_questions",
    "business_rules",
)

IMPORT_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "running",
    "success",
    "partial_success",
    "failed",
)


def _as_sql_values(values: tuple[str, ...]) -> str:
    """Return a comma-separated SQL string literal list."""

    return ", ".join(f"'{value}'" for value in values)


class DataImportBatch(TimestampMixin, Base):
    """One source-file import execution record.

    A failed import may be retried with the same source hash. Non-failed
    imports keep a partial unique index to prevent duplicate active/successful
    processing of the same source file.
    """

    __tablename__ = "data_import_batches"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    batch_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid4,
        unique=True,
        nullable=False,
    )
    data_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    source_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    source_sha256: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
    )
    record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending",
    )
    error_summary: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            f"data_type IN ({_as_sql_values(IMPORT_DATA_TYPES)})",
            name="data_type_allowed",
        ),
        CheckConstraint(
            f"status IN ({_as_sql_values(IMPORT_STATUSES)})",
            name="status_allowed",
        ),
        CheckConstraint(
            "record_count >= 0",
            name="record_count_non_negative",
        ),
        CheckConstraint(
            "success_count >= 0",
            name="success_count_non_negative",
        ),
        CheckConstraint(
            "failed_count >= 0",
            name="failed_count_non_negative",
        ),
        CheckConstraint(
            "success_count + failed_count <= record_count",
            name="processed_count_not_greater_than_record_count",
        ),
        CheckConstraint(
            "source_sha256 ~ '^[0-9A-Fa-f]{64}$'",
            name="source_sha256_format",
        ),
        Index(
            "ix_data_import_batches_data_type_status",
            "data_type",
            "status",
        ),
        Index(
            "ix_data_import_batches_started_at",
            "started_at",
        ),
        Index(
            "uq_data_import_batches_active_source",
            "data_type",
            "source_sha256",
            unique=True,
            postgresql_where=text(
                "status IN "
                "('pending', 'running', 'success', 'partial_success')"
            ),
        ),
    )