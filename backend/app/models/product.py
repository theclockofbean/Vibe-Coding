"""Product master-data ORM model.

The products table stores normalized SKU data imported from sku_master.xlsx.
Structured product facts must be queried from this table rather than inferred
by an LLM.
"""

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Product(TimestampMixin, Base):
    """Represent one normalized product SKU."""

    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "btrim(sku_id) <> ''",
            name="sku_id_not_blank",
        ),
        CheckConstraint(
            "btrim(product_name) <> ''",
            name="product_name_not_blank",
        ),
        CheckConstraint(
            "btrim(thread_spec) <> ''",
            name="thread_spec_not_blank",
        ),
        CheckConstraint(
            "thread_type = 'M'",
            name="thread_type_metric",
        ),
        CheckConstraint(
            "thread_diameter_mm > 0",
            name="thread_diameter_positive",
        ),
        CheckConstraint(
            "thread_pitch_mm > 0",
            name="thread_pitch_positive",
        ),
        CheckConstraint(
            "rod_length_mm > 0",
            name="rod_length_positive",
        ),
        CheckConstraint(
            "ball_diameter_mm > 0",
            name="ball_diameter_positive",
        ),
        CheckConstraint(
            (
                "taper_ratio IS NULL "
                "OR taper_ratio ~ '^1:[1-9][0-9]*$'"
            ),
            name="taper_ratio_format",
        ),
        CheckConstraint(
            "btrim(material) <> ''",
            name="material_not_blank",
        ),
        CheckConstraint(
            "btrim(surface_treatment) <> ''",
            name="surface_treatment_not_blank",
        ),
        CheckConstraint(
            "btrim(oem_reference_number) <> ''",
            name="oem_reference_number_not_blank",
        ),
        CheckConstraint(
            "min_order_qty > 0",
            name="min_order_qty_positive",
        ),
        CheckConstraint(
            "btrim(stock_status) <> ''",
            name="stock_status_not_blank",
        ),
        CheckConstraint(
            "lead_time_days >= 0",
            name="lead_time_days_non_negative",
        ),
        CheckConstraint(
            "source_row_number IS NULL OR source_row_number > 0",
            name="source_row_number_positive",
        ),
        UniqueConstraint(
            "sku_id",
            name="uq_products_sku_id",
        ),
        Index(
            "ix_products_thread_spec",
            "thread_spec",
        ),
        Index(
            "ix_products_thread_diameter_mm",
            "thread_diameter_mm",
        ),
        Index(
            "ix_products_thread_pitch_mm",
            "thread_pitch_mm",
        ),
        Index(
            "ix_products_material",
            "material",
        ),
        Index(
            "ix_products_stock_status",
            "stock_status",
        ),
        Index(
            "ix_products_oem_reference_number",
            "oem_reference_number",
        ),
        Index(
            "ix_products_is_active",
            "is_active",
        ),
        Index(
            "ix_products_import_batch_id",
            "import_batch_id",
        ),
        Index(
            "ix_products_thread_lookup",
            "thread_diameter_mm",
            "thread_pitch_mm",
            "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    sku_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    thread_spec: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    thread_type: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="M",
        server_default="M",
    )

    thread_diameter_mm: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )

    thread_pitch_mm: Mapped[Decimal] = mapped_column(
        Numeric(6, 3),
        nullable=False,
    )

    rod_length_mm: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )

    ball_diameter_mm: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )

    taper_ratio: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    material: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    surface_treatment: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    oem_reference_number: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    min_order_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    stock_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
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

    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_row_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


__all__ = ["Product"]