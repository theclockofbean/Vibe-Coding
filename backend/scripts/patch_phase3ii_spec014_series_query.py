"""Add product-name keyword spec query for series-style questions."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

ROUTER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/routers/unified_intent_router.py"
PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"
HANDLER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/handlers/spec_handler.py"
SERVICE_FILE: Final[Path] = BACKEND_ROOT / "app/services/spec_query_service.py"
REPOSITORY_FILE: Final[Path] = BACKEND_ROOT / "app/repositories/product_repository.py"
RENDERER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/renderers/spec_answer_renderer.py"


def replace_once(
    content: str,
    old: str,
    new: str,
    label: str,
    changes: list[str],
    errors: list[str],
) -> str:
    """Replace one block idempotently."""

    if new in content:
        changes.append(f"{label} already patched")
        return content

    if old not in content:
        errors.append(f"{label} anchor not found")
        return content

    changes.append(f"patched {label}")
    return content.replace(old, new, 1)


def patch_file(path: Path, patches: list[tuple[str, str, str]]) -> tuple[list[str], list[str]]:
    """Apply patches to one file."""

    content = path.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []
    errors: list[str] = []

    for label, old, new in patches:
        content = replace_once(content, old, new, label, changes, errors)

    if content != original and not errors:
        path.write_text(content, encoding="utf-8")

    return changes, errors


def main() -> int:
    """Patch all layers."""

    all_changes: list[str] = []
    all_errors: list[str] = []

    patches_by_file: dict[Path, list[tuple[str, str, str]]] = {
        ROUTER_FILE: [
            (
                "router spec series signals",
                '''        "型号",
    ),
''',
                '''        "型号",
        "系列",
        "都一样",
        "夜光",
    ),
''',
            ),
        ],
        PARSER_FILE: [
            (
                "parser query type",
                '''    "oem_reference_number",
]
''',
                '''    "oem_reference_number",
    "product_name_keyword",
]
''',
            ),
            (
                "parser extract keyword variable",
                '''        material_keyword = self.extract_material_keyword(normalized_text)

        warnings = self._build_priority_warnings(
''',
                '''        material_keyword = self.extract_material_keyword(normalized_text)
        product_name_keyword = self.extract_product_name_keyword(normalized_text)

        warnings = self._build_priority_warnings(
''',
            ),
            (
                "parser product keyword branch",
                '''        if material_keyword is not None:
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="material_keyword",
                query_value=material_keyword,
                limit=limit,
                warnings=warnings,
            )

        return ParsedSpecQuery(
''',
                '''        if material_keyword is not None:
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="material_keyword",
                query_value=material_keyword,
                limit=limit,
                warnings=warnings,
            )

        if product_name_keyword is not None:
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="product_name_keyword",
                query_value=product_name_keyword,
                limit=limit,
                warnings=warnings,
            )

        return ParsedSpecQuery(
''',
            ),
            (
                "parser product keyword helper",
                '''    @staticmethod
    def is_max_rod_length_query(
''',
                '''    @staticmethod
    def extract_product_name_keyword(
        text: str,
    ) -> str | None:
        """Extract supported product name or series keyword."""

        for keyword in ("夜光",):
            if keyword in text and (
                "系列" in text
                or "螺纹" in text
                or "规格" in text
                or "球头" in text
            ):
                return keyword

        return None

    @staticmethod
    def is_max_rod_length_query(
''',
            ),
        ],
        HANDLER_FILE: [
            (
                "handler query type",
                '''    "oem_reference_number",
]
''',
                '''    "oem_reference_number",
    "product_name_keyword",
]
''',
            ),
            (
                "handler product keyword branch",
                '''        if handler_input.query_type == "max_rod_length":
            return self._spec_query_service.query_by_max_rod_length(
                limit=handler_input.limit,
            )
''',
                '''        if handler_input.query_type == "product_name_keyword":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_product_name_keyword(
                query_value,
                limit=max(handler_input.limit, 50),
            )

        if handler_input.query_type == "max_rod_length":
            return self._spec_query_service.query_by_max_rod_length(
                limit=handler_input.limit,
            )
''',
            ),
        ],
        SERVICE_FILE: [
            (
                "service product keyword query",
                '''    def query_by_max_rod_length(
''',
                '''    def query_by_product_name_keyword(
        self,
        product_name_keyword: str,
        *,
        limit: int = 50,
    ) -> SpecQueryResult:
        """Query product facts by product name keyword."""

        normalized_keyword = product_name_keyword.strip()
        products = self._product_repository.list_by_product_name_keyword(
            normalized_keyword,
            limit=limit,
        )

        return self._build_result(
            query_type="product_name_keyword",
            query_value=normalized_keyword,
            products=products,
        )

    def query_by_max_rod_length(
''',
            ),
        ],
        REPOSITORY_FILE: [
            (
                "repository product keyword query",
                '''    def list_by_max_rod_length(
''',
                '''    def list_by_product_name_keyword(
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

    def list_by_max_rod_length(
''',
            ),
        ],
        RENDERER_FILE: [
            (
                "renderer product keyword dispatch",
                '''        if len(products) == 1:
            text = self._render_single_product(products[0])
        else:
            text = self._render_multiple_products(products)
''',
                '''        query_type = str(facts.get("query_type") or "")

        if query_type == "product_name_keyword":
            query_value = str(facts.get("query_value") or "")
            text = self._render_product_name_keyword(products, query_value)
        elif len(products) == 1:
            text = self._render_single_product(products[0])
        else:
            text = self._render_multiple_products(products)
''',
            ),
            (
                "renderer product keyword helper",
                '''    @staticmethod
    def _render_multiple_products(products: list[dict[str, Any]]) -> str:
''',
                '''    @staticmethod
    def _render_product_name_keyword(
        products: list[dict[str, Any]],
        keyword: str,
    ) -> str:
        """Render product-name keyword spec comparison."""

        lines = [
            f"按产品名称关键词“{keyword}”查到 {len(products)} 个具体SKU：",
        ]

        thread_specs = sorted(
            {
                str(product["thread_spec"])
                for product in products
            }
        )

        for product in products:
            lines.append(
                "- "
                f"{product['sku_id']}｜{product['product_name']}｜"
                f"螺纹规格 {product['thread_spec']}｜"
                f"杆长 {product['rod_length_mm']} mm｜"
                f"球径 {product['ball_diameter_mm']} mm"
            )

        if len(thread_specs) > 1:
            lines.append(
                "这些具体SKU的螺纹规格不完全一样，包含："
                + "、".join(thread_specs)
                + "。建议按具体SKU查询后再确认。"
            )
        else:
            lines.append(
                "这些具体SKU当前查到的螺纹规格一致，为 "
                + "、".join(thread_specs)
                + "。建议下单前仍按具体SKU查询确认。"
            )

        return "\\n".join(lines)

    @staticmethod
    def _render_multiple_products(products: list[dict[str, Any]]) -> str:
''',
            ),
        ],
    }

    for path, patches in patches_by_file.items():
        changes, errors = patch_file(path, patches)
        all_changes.extend(f"{path.name}: {change}" for change in changes)
        all_errors.extend(f"{path.name}: {error}" for error in errors)

    pprint({"changes": all_changes, "errors": all_errors})
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())