"""Patch repository and spec query service with structured query capabilities."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

REPOSITORY_FILE: Final[Path] = BACKEND_ROOT / "app/repositories/product_repository.py"
SERVICE_FILE: Final[Path] = BACKEND_ROOT / "app/services/spec_query_service.py"


REPOSITORY_METHODS: Final[str] = '''
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

'''


SERVICE_METHODS: Final[str] = '''
    def query_by_thread_diameter(
        self,
        *,
        diameter_mm: Decimal,
        limit: int = 50,
    ) -> SpecQueryResult:
        """Query product facts by metric thread diameter only."""

        products = self._product_repository.list_by_thread_diameter(
            diameter_mm=diameter_mm,
            limit=limit,
        )

        return self._build_result(
            query_type="thread_diameter",
            query_value=f"M{self._normalize_decimal_text(str(diameter_mm))}",
            products=products,
        )

    def query_by_material_keyword(
        self,
        material_keyword: str,
        *,
        limit: int = 50,
    ) -> SpecQueryResult:
        """Query product facts by material keyword."""

        normalized_keyword = material_keyword.strip()
        products = self._product_repository.list_by_material_keyword(
            normalized_keyword,
            limit=limit,
        )

        return self._build_result(
            query_type="material_keyword",
            query_value=normalized_keyword,
            products=products,
        )

    def query_by_max_rod_length(
        self,
        *,
        limit: int = 10,
    ) -> SpecQueryResult:
        """Query products ordered by maximum rod length."""

        products = self._product_repository.list_by_max_rod_length(limit=limit)

        return self._build_result(
            query_type="max_rod_length",
            query_value="max_rod_length",
            products=products,
        )

    def query_by_max_ball_diameter(
        self,
        *,
        limit: int = 10,
    ) -> SpecQueryResult:
        """Query products ordered by maximum ball diameter."""

        products = self._product_repository.list_by_max_ball_diameter(limit=limit)

        return self._build_result(
            query_type="max_ball_diameter",
            query_value="max_ball_diameter",
            products=products,
        )

'''


def main() -> int:
    """Patch service capabilities."""

    print("=" * 80)
    print("patching Phase 3-I-I spec query service capabilities")

    errors: list[str] = []
    changes: list[str] = []

    patch_repository(errors=errors, changes=changes)
    patch_service(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec query service capability patch failed")
        return 1

    print("Phase 3-I-I spec query service capability patch completed")
    return 0


def patch_repository(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch ProductRepository."""

    if not REPOSITORY_FILE.exists():
        errors.append(f"missing repository file: {REPOSITORY_FILE}")
        return

    content = REPOSITORY_FILE.read_text(encoding="utf-8")
    original = content

    if "from decimal import Decimal" not in content:
        anchor = "from collections.abc import Iterable\n"
        if anchor in content:
            content = content.replace(anchor, anchor + "from decimal import Decimal\n", 1)
            changes.append("added Decimal import to product_repository")
        else:
            errors.append("repository import anchor not found")

    if "def list_by_thread_diameter(" not in content:
        anchor = "    def list_active_products(\n"
        if anchor not in content:
            errors.append("list_active_products anchor not found")
        else:
            content = content.replace(anchor, REPOSITORY_METHODS + anchor, 1)
            changes.append("inserted repository structured query methods")
    else:
        changes.append("repository structured query methods already present")

    if content != original and not errors:
        REPOSITORY_FILE.write_text(content, encoding="utf-8")


def patch_service(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch SpecQueryService."""

    if not SERVICE_FILE.exists():
        errors.append(f"missing service file: {SERVICE_FILE}")
        return

    content = SERVICE_FILE.read_text(encoding="utf-8")
    original = content

    if "def query_by_thread_diameter(" not in content:
        anchor = "    def query_by_oem_reference(\n"
        if anchor not in content:
            errors.append("query_by_oem_reference anchor not found")
        else:
            content = content.replace(anchor, SERVICE_METHODS + anchor, 1)
            changes.append("inserted service structured query methods")
    else:
        changes.append("service structured query methods already present")

    if content != original and not errors:
        SERVICE_FILE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())