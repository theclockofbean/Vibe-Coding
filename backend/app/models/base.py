"""SQLAlchemy declarative base and shared model mixins.

This module defines the common SQLAlchemy metadata and timestamp columns used
by all ORM models in the project. It must not contain business-specific tables.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class inherited by every SQLAlchemy ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Add creation and modification timestamps to an ORM model.

    PostgreSQL stores these columns as TIMESTAMPTZ because ``timezone=True``
    is enabled. The database supplies the initial timestamp, while SQLAlchemy
    updates ``updated_at`` whenever an ORM UPDATE statement is emitted.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = [
    "Base",
    "NAMING_CONVENTION",
    "TimestampMixin",
]