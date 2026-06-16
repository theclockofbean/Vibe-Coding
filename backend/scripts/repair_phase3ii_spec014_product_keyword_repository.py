"""Repair product name keyword repository query expansion."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

REPOSITORY_FILE = Path("app/repositories/product_repository.py")


NEW_METHOD = '''    def list_by_product_name_keyword(
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
'''


def main() -> int:
    content = REPOSITORY_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    start_marker = "    def list_by_product_name_keyword("
    start = content.find(start_marker)

    if start == -1:
        errors.append("list_by_product_name_keyword method not found")
    else:
        next_method = content.find("\n    def ", start + len(start_marker))

        if next_method == -1:
            errors.append("next repository method anchor not found")
        else:
            content = content[:start] + NEW_METHOD + content[next_method:]
            REPOSITORY_FILE.write_text(content, encoding="utf-8")
            changes.append("replaced product name keyword method")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())