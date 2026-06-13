"""Structured specification query service.

This service converts product records into controlled structured facts.
It does not call an LLM and does not invent SKU, OEM, stock, logistics, or
pricing information.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Final

from app.models.product import Product
from app.repositories import ProductRepository

THREAD_SPEC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^M(?P<diameter>\d+(?:\.\d+)?)\s*[×xX*＊]\s*(?P<pitch>\d+(?:\.\d+)?)$"
)


@dataclass(frozen=True)
class ProductSpecFact:
    """Controlled product specification facts from the products table."""

    sku_id: str
    product_name: str
    thread_spec: str
    thread_diameter_mm: str
    thread_pitch_mm: str
    rod_length_mm: str
    ball_diameter_mm: str
    taper_ratio: str | None
    material: str
    surface_treatment: str
    oem_reference_number: str
    min_order_qty: int
    stock_status: str
    lead_time_days: int


@dataclass(frozen=True)
class SpecQueryResult:
    """Structured result returned by the spec query service."""

    query_type: str
    query_value: str
    matched_count: int
    products: list[ProductSpecFact]
    source_table: str = "products"
    handoff_required: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return {
            "query_type": self.query_type,
            "query_value": self.query_value,
            "matched_count": self.matched_count,
            "products": [
                asdict(product)
                for product in self.products
            ],
            "source_table": self.source_table,
            "handoff_required": self.handoff_required,
        }


class SpecQueryService:
    """Read-only structured product specification query service."""

    def __init__(self, product_repository: ProductRepository) -> None:
        """Initialize service with a product repository."""

        self._product_repository = product_repository

    def query_by_sku(
        self,
        sku_id: str,
    ) -> SpecQueryResult:
        """Query product facts by SKU ID."""

        normalized_sku_id = self.normalize_sku_id(sku_id)
        product = self._product_repository.get_by_sku_id(normalized_sku_id)

        return self._build_result(
            query_type="sku_id",
            query_value=normalized_sku_id,
            products=[] if product is None else [product],
        )

    def query_by_sku_ids(
        self,
        sku_ids: list[str],
    ) -> SpecQueryResult:
        """Query product facts by multiple SKU IDs."""

        normalized_sku_ids = [
            self.normalize_sku_id(sku_id)
            for sku_id in sku_ids
            if sku_id.strip()
        ]

        products = self._product_repository.list_by_sku_ids(
            normalized_sku_ids
        )

        return self._build_result(
            query_type="sku_ids",
            query_value=",".join(normalized_sku_ids),
            products=products,
        )

    def query_by_thread_spec(
        self,
        thread_spec: str,
        *,
        limit: int = 20,
    ) -> SpecQueryResult:
        """Query product facts by thread spec such as M8×1.25."""

        normalized_thread_spec = self.normalize_thread_spec(thread_spec)
        products = self._product_repository.list_by_thread_spec(
            normalized_thread_spec,
            limit=limit,
        )

        return self._build_result(
            query_type="thread_spec",
            query_value=normalized_thread_spec,
            products=products,
        )

    def query_by_thread_dimensions(
        self,
        *,
        diameter_mm: Decimal,
        pitch_mm: Decimal,
        limit: int = 20,
    ) -> SpecQueryResult:
        """Query product facts by metric thread diameter and pitch."""

        products = self._product_repository.list_by_thread_dimensions(
            diameter_mm=diameter_mm,
            pitch_mm=pitch_mm,
            limit=limit,
        )

        return self._build_result(
            query_type="thread_dimensions",
            query_value=f"M{diameter_mm}×{pitch_mm}",
            products=products,
        )

    def query_by_oem_reference(
        self,
        oem_reference_number: str,
    ) -> SpecQueryResult:
        """Query product facts by exact OEM reference number."""

        normalized_oem = oem_reference_number.strip()
        product = self._product_repository.get_by_oem_reference(normalized_oem)

        return self._build_result(
            query_type="oem_reference_number",
            query_value=normalized_oem,
            products=[] if product is None else [product],
        )

    @staticmethod
    def normalize_sku_id(sku_id: str) -> str:
        """Normalize SKU ID for exact lookup."""

        return sku_id.strip().upper()

    @classmethod
    def normalize_thread_spec(cls, thread_spec: str) -> str:
        """Normalize thread spec input to canonical multiplication sign."""

        value = thread_spec.strip().upper()
        match = THREAD_SPEC_PATTERN.fullmatch(value)

        if match is None:
            return value

        diameter = cls._normalize_decimal_text(match.group("diameter"))
        pitch = cls._normalize_decimal_text(match.group("pitch"))

        return f"M{diameter}×{pitch}"

    @staticmethod
    def _normalize_decimal_text(value: str) -> str:
        """Normalize decimal text without scientific notation."""

        decimal_value = Decimal(value)

        normalized = format(decimal_value.normalize(), "f")

        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")

        return normalized

    @staticmethod
    def product_to_fact(product: Product) -> ProductSpecFact:
        """Convert one Product ORM object into controlled product facts."""

        return ProductSpecFact(
            sku_id=product.sku_id,
            product_name=product.product_name,
            thread_spec=product.thread_spec,
            thread_diameter_mm=str(product.thread_diameter_mm),
            thread_pitch_mm=str(product.thread_pitch_mm),
            rod_length_mm=str(product.rod_length_mm),
            ball_diameter_mm=str(product.ball_diameter_mm),
            taper_ratio=product.taper_ratio,
            material=product.material,
            surface_treatment=product.surface_treatment,
            oem_reference_number=product.oem_reference_number,
            min_order_qty=product.min_order_qty,
            stock_status=product.stock_status,
            lead_time_days=product.lead_time_days,
        )

    def _build_result(
        self,
        *,
        query_type: str,
        query_value: str,
        products: list[Product],
    ) -> SpecQueryResult:
        """Build a structured query result."""

        product_facts = [
            self.product_to_fact(product)
            for product in products
        ]

        return SpecQueryResult(
            query_type=query_type,
            query_value=query_value,
            matched_count=len(product_facts),
            products=product_facts,
        )