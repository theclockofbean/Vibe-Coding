"""Expand product name keyword query for luminous/night-glow series."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

REPOSITORY_FILE = Path("app/repositories/product_repository.py")


OLD_IMPORT = "from sqlalchemy import select\n"
NEW_IMPORT = "from sqlalchemy import or_, select\n"


OLD_METHOD = '''    def list_by_product_name_keyword(
        self,
        product_name_keyword: str,
        *,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products whose product name contains the keyword."""

        keyword = product_name_keyword.strip()

        if not keyword:
            return []

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = select(Product).where(Product.product_name.contains(keyword))

        if active_only:
            statement = statement.where(Product.is_active.is_(True))

        statement = statement.order_by(Product.sku_id).limit(limit)

        return list(self._session.scalars(statement).all())
'''


NEW_METHOD = '''    def list_by_product_name_keyword(
        self,
        product_name_keyword: str,
        *,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Product]:
        """Return products whose product name matches the keyword family."""

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
'''


def main() -> int:
    content = REPOSITORY_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_IMPORT in content:
        content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
        changes.append("added sqlalchemy or_ import")
    elif "from sqlalchemy import or_, select" in content:
        changes.append("or_ import already present")
    else:
        errors.append("sqlalchemy select import anchor not found")

    if OLD_METHOD in content:
        content = content.replace(OLD_METHOD, NEW_METHOD, 1)
        changes.append("expanded 夜光 product keyword family")
    elif 'keywords = ["夜光", "发光", "荧光"]' in content:
        changes.append("夜光 keyword family already expanded")
    else:
        errors.append("list_by_product_name_keyword anchor not found")

    if not errors:
        REPOSITORY_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())