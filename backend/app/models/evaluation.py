"""Evaluation case, run, and result ORM models.

Evaluation cases define the expected system behaviour. Evaluation runs group
one complete execution of the dataset, and evaluation results store the
outcome of each case within a run.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

EVALUATION_SCENARIO_TYPES: Final[tuple[str, ...]] = (
    "core",
    "boundary",
    "risk",
)

EVALUATION_CATEGORIES: Final[tuple[str, ...]] = (
    "spec",
    "quality",
    "price",
    "logistics",
    "escalation",
)

EVALUATION_INTENTS: Final[tuple[str, ...]] = (
    *EVALUATION_CATEGORIES,
    "unknown",
)

EVALUATION_DIFFICULTIES: Final[tuple[str, ...]] = (
    "easy",
    "medium",
    "hard",
)

EVALUATION_SOURCES: Final[tuple[str, ...]] = (
    "manual",
    "real_chat",
)

EVALUATION_VERIFICATION_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "verified",
    "rejected",
)

EVALUATION_RUN_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
)


def _as_sql_values(values: tuple[str, ...]) -> str:
    """Convert trusted constant values into a SQL CHECK value list."""

    return ", ".join(f"'{value}'" for value in values)


class EvaluationCase(TimestampMixin, Base):
    """Represent one expected-behaviour test case."""

    __tablename__ = "evaluation_cases"

    __table_args__ = (
        CheckConstraint(
            "btrim(case_id) <> ''",
            name="case_id_not_blank",
        ),
        CheckConstraint(
            (
                "scenario_type IN "
                f"({_as_sql_values(EVALUATION_SCENARIO_TYPES)})"
            ),
            name="scenario_type_allowed",
        ),
        CheckConstraint(
            f"category IN ({_as_sql_values(EVALUATION_CATEGORIES)})",
            name="category_allowed",
        ),
        CheckConstraint(
            (
                "difficulty IN "
                f"({_as_sql_values(EVALUATION_DIFFICULTIES)})"
            ),
            name="difficulty_allowed",
        ),
        CheckConstraint(
            f"source IN ({_as_sql_values(EVALUATION_SOURCES)})",
            name="source_allowed",
        ),
        CheckConstraint(
            (
                "expected_intent IN "
                f"({_as_sql_values(EVALUATION_INTENTS)})"
            ),
            name="expected_intent_allowed",
        ),
        CheckConstraint(
            "btrim(input_message) <> ''",
            name="input_message_not_blank",
        ),
        CheckConstraint(
            "btrim(expected_answer) <> ''",
            name="expected_answer_not_blank",
        ),
        CheckConstraint(
            (
                "human_score_target IS NULL "
                "OR (human_score_target >= 0 "
                "AND human_score_target <= 5)"
            ),
            name="human_score_target_range",
        ),
        CheckConstraint(
            (
                "verification_status IN "
                f"({_as_sql_values(EVALUATION_VERIFICATION_STATUSES)})"
            ),
            name="verification_status_allowed",
        ),
        UniqueConstraint(
            "case_id",
            name="uq_evaluation_cases_case_id",
        ),
        Index(
            "ix_evaluation_cases_scenario_type",
            "scenario_type",
        ),
        Index(
            "ix_evaluation_cases_category",
            "category",
        ),
        Index(
            "ix_evaluation_cases_difficulty",
            "difficulty",
        ),
        Index(
            "ix_evaluation_cases_expected_handoff",
            "expected_handoff",
        ),
        Index(
            "ix_evaluation_cases_is_critical",
            "is_critical",
        ),
        Index(
            "ix_evaluation_cases_verification_status",
            "verification_status",
        ),
        Index(
            "ix_evaluation_cases_import_batch_id",
            "import_batch_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    scenario_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    difficulty: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    input_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    expected_intent: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    expected_handoff: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    expected_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    expected_sku_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::varchar[]"),
    )

    must_contain_all: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )

    must_contain_any: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )

    must_not_contain: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )

    allowed_phrases: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )

    expected_source: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )

    is_critical: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    human_score_target: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1),
        nullable=True,
    )

    verification_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    import_batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "data_import_batches.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="evaluation_case",
        passive_deletes=True,
    )


class EvaluationRun(TimestampMixin, Base):
    """Represent one complete evaluation dataset execution."""

    __tablename__ = "evaluation_runs"

    __table_args__ = (
        CheckConstraint(
            "btrim(system_version) <> ''",
            name="system_version_not_blank",
        ),
        CheckConstraint(
            f"status IN ({_as_sql_values(EVALUATION_RUN_STATUSES)})",
            name="status_allowed",
        ),
        CheckConstraint(
            "total_cases >= 0",
            name="total_cases_non_negative",
        ),
        CheckConstraint(
            "completed_cases >= 0",
            name="completed_cases_non_negative",
        ),
        CheckConstraint(
            "passed_cases >= 0",
            name="passed_cases_non_negative",
        ),
        CheckConstraint(
            "failed_cases >= 0",
            name="failed_cases_non_negative",
        ),
        CheckConstraint(
            "completed_cases <= total_cases",
            name="completed_cases_not_greater_than_total",
        ),
        CheckConstraint(
            "passed_cases + failed_cases <= completed_cases",
            name="result_count_not_greater_than_completed",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_at_not_before_started_at",
        ),
        UniqueConstraint(
            "run_id",
            name="uq_evaluation_runs_run_id",
        ),
        Index(
            "ix_evaluation_runs_status",
            "status",
        ),
        Index(
            "ix_evaluation_runs_system_version",
            "system_version",
        ),
        Index(
            "ix_evaluation_runs_started_at",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        default=uuid4,
    )

    system_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    dataset_version: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    total_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    completed_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    passed_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    failed_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    config_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    summary_metrics: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvaluationResult(TimestampMixin, Base):
    """Store the outcome of one case within one evaluation run."""

    __tablename__ = "evaluation_results"

    __table_args__ = (
        CheckConstraint(
            (
                "actual_intent IS NULL "
                f"OR actual_intent IN ({_as_sql_values(EVALUATION_INTENTS)})"
            ),
            name="actual_intent_allowed",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="latency_ms_non_negative",
        ),
        CheckConstraint(
            (
                "human_score IS NULL "
                "OR (human_score >= 0 AND human_score <= 5)"
            ),
            name="human_score_range",
        ),
        UniqueConstraint(
            "evaluation_run_id",
            "evaluation_case_id",
            name="uq_evaluation_results_run_case",
        ),
        Index(
            "ix_evaluation_results_evaluation_run_id",
            "evaluation_run_id",
        ),
        Index(
            "ix_evaluation_results_evaluation_case_id",
            "evaluation_case_id",
        ),
        Index(
            "ix_evaluation_results_intent_correct",
            "intent_correct",
        ),
        Index(
            "ix_evaluation_results_handoff_correct",
            "handoff_correct",
        ),
        Index(
            "ix_evaluation_results_critical_passed",
            "critical_passed",
        ),
        Index(
            "ix_evaluation_results_created_at",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    evaluation_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "evaluation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    evaluation_case_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "evaluation_cases.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    actual_intent: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    actual_handoff: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    actual_answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    actual_sku_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::varchar[]"),
    )

    intent_correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    handoff_correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    sku_correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    contains_all_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    contains_any_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    excludes_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    critical_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    human_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    raw_result: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    evaluation_run: Mapped[EvaluationRun] = relationship(
        back_populates="results",
    )

    evaluation_case: Mapped[EvaluationCase] = relationship(
        back_populates="results",
    )


__all__ = [
    "EVALUATION_CATEGORIES",
    "EVALUATION_DIFFICULTIES",
    "EVALUATION_INTENTS",
    "EVALUATION_RUN_STATUSES",
    "EVALUATION_SCENARIO_TYPES",
    "EVALUATION_SOURCES",
    "EVALUATION_VERIFICATION_STATUSES",
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationRun",
]