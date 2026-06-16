"""Product query repository.

This module provides read-only product lookup methods for the spec handler.
It must not invent product facts. All returned facts come from the products
table.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductRepository:
    """Read-only repository for product facts."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with an existing SQLAlchemy session."""

        self._session = session

    def count_active_products(self) -> int:
        """Return count of active products."""

        statement = select(func.count()).select_from(Product).where(
            Product.is_active.is_(True)
        )

        return int(self._session.execute(statement).scalar_one())

    def get_by_sku_id(
        self,
        sku_id: str,
        *,
        active_only: bool = True,
    ) -> Product | None:
        """Return one product by exact SKU ID."""

        statement = select(Product).where(Product.sku_id == sku_id)

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        return self._session.execute(statement).scalar_one_or_none()

    def list_by_sku_ids(
        self,
        sku_ids: Iterable[str],
        *,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products matching the provided SKU IDs."""

        normalized_sku_ids = [
            sku_id.strip()
            for sku_id in sku_ids
            if sku_id.strip()
        ]

        if not normalized_sku_ids:
            return []

        statement = select(Product).where(Product.sku_id.in_(normalized_sku_ids))

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id)

        return list(self._session.scalars(statement).all())

    def list_by_thread_spec(
        self,
        thread_spec: str,
        *,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[Product]:
        """Return products matching an exact thread spec."""

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product).where(Product.thread_spec == thread_spec)

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id).limit(limit)

        return list(self._session.scalars(statement).all())

    def list_by_thread_dimensions(
        self,
        *,
        diameter_mm: Decimal,
        pitch_mm: Decimal,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[Product]:
        """Return products matching metric thread diameter and pitch."""

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product).where(
            Product.thread_type == "M",
            Product.thread_diameter_mm == diameter_mm,
            Product.thread_pitch_mm == pitch_mm,
        )

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id).limit(limit)

        return list(self._session.scalars(statement).all())

    def get_by_oem_reference(
        self,
        oem_reference_number: str,
        *,
        active_only: bool = True,
    ) -> Product | None:
        """Return one product by exact OEM reference number."""

        statement = select(Product).where(
            Product.oem_reference_number == oem_reference_number
        )

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        return self._session.execute(statement).scalar_one_or_none()


    def list_by_thread_diameter(
        self,
        diameter_mm: Decimal,
        *,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products matching metric thread diameter."""

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product).where(
            Product.thread_type == "M",
            Product.thread_diameter_mm == diameter_mm,
        )

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id).limit(limit)

        return list(self._session.scalars(statement).all())

    def list_by_material_keyword(
        self,
        material_keyword: str,
        *,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products whose material contains the keyword."""

        keyword = material_keyword.strip()

        if not keyword:
            return []

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product).where(Product.material.contains(keyword))

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id).limit(limit)

        return list(self._session.scalars(statement).all())

    def list_by_product_name_keyword(
        self,
        product_name_keyword: str,
        *,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products whose product name matches the keyword family."""

        from sqlalchemy import or_

        keyword = product_name_keyword.strip()

        if not keyword:
            return []

        if limit <= 0:
            raise ValueError("limit must be positive")

        keywords = [keyword]

        if keyword == "夜光":
            keywords = ["夜光", "发光", "荧光"]

        statement = select(Product).where(
            or_(*(Product.product_name.contains(item) for item in keywords)),
        )

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id).limit(limit)

        return list(self._session.scalars(statement).all())

    def list_by_max_rod_length(
        self,
        *,
        limit: int = 10,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products with the maximum rod length."""

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product)

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(
            Product.rod_length_mm.desc(),
            Product.sku_id,
        ).limit(limit)

        return list(self._session.scalars(statement).all())

    def list_by_max_ball_diameter(
        self,
        *,
        limit: int = 10,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products with the maximum ball diameter."""

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product)

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(
            Product.ball_diameter_mm.desc(),
            Product.sku_id,
        ).limit(limit)

        return list(self._session.scalars(statement).all())

    def list_active_products(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Return active products with simple pagination."""

        if limit <= 0:
            raise ValueError("limit must be positive")

        if offset < 0:
            raise ValueError("offset must be non-negative")

        statement = (
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.sku_id)
            .limit(limit)
            .offset(offset)
        )

        return list(self._session.scalars(statement).all())