"""Quality intent handler.

This handler receives ParsedQualityQuery and converts it into a unified
HandlerResult.

It may read product facts from the products table, but it does not generate
customer-facing text, call an LLM, promise durability, promise rust resistance,
promise scratch resistance, promise warranty, promise returns/exchanges,
promise compensation, judge quality responsibility, or write data.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from app.agent.parsers import ParsedQualityQuery
from app.agent.types import HandlerResult, HandlerStatus, SourceReference
from app.repositories import ProductRepository

QualityHandlerResult: TypeAlias = HandlerResult


AUTO_SUCCESS_QUERY_TYPES = {
    "material",
    "surface_treatment",
}


class QualityHandler:
    """Handle structured quality queries."""

    handler_name = "quality_handler"
    primary_intent = "quality"

    def __init__(
        self,
        *,
        product_repository: ProductRepository,
    ) -> None:
        """Initialize handler with product repository."""

        self._product_repository = product_repository

    def handle(self, parsed_query: ParsedQualityQuery) -> HandlerResult:
        """Handle one parsed quality query."""

        if parsed_query.status == "parsed":
            return self._handle_parsed(parsed_query)

        if parsed_query.status == "missing_product_reference":
            return self._missing_reference_result(parsed_query)

        if parsed_query.status == "ambiguous":
            return self._invalid_request_result(parsed_query)

        if parsed_query.status == "not_quality_intent":
            return self._invalid_request_result(parsed_query)

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="failed",
            matched_count=0,
            handoff_required=True,
            facts=None,
            errors=["unsupported quality parse status"],
            source_references=[],
        )

    def _handle_parsed(
        self,
        parsed_query: ParsedQualityQuery,
    ) -> HandlerResult:
        """Handle parsed quality query with product reference."""

        products = self._query_products(parsed_query)

        if not products:
            return HandlerResult(
                primary_intent=self.primary_intent,
                handler_name=self.handler_name,
                status="not_found",
                matched_count=0,
                handoff_required=True,
                facts=self._build_facts(
                    parsed_query=parsed_query,
                    products=[],
                ),
                errors=["product not found"],
                source_references=[],
            )

        status, handoff_required = self._resolve_status(
            parsed_query=parsed_query,
            products=products,
        )

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status=status,
            matched_count=len(products),
            handoff_required=handoff_required,
            facts=self._build_facts(
                parsed_query=parsed_query,
                products=products,
            ),
            errors=[],
            source_references=self._build_source_references(products),
        )

    def _missing_reference_result(
        self,
        parsed_query: ParsedQualityQuery,
    ) -> HandlerResult:
        """Return handoff result when quality intent lacks product reference."""

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="handoff",
            matched_count=0,
            handoff_required=True,
            facts=self._build_facts(
                parsed_query=parsed_query,
                products=[],
            ),
            errors=parsed_query.errors,
            source_references=[],
        )

    def _invalid_request_result(
        self,
        parsed_query: ParsedQualityQuery,
    ) -> HandlerResult:
        """Return invalid request result for unsupported parser states."""

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="invalid_request",
            matched_count=0,
            handoff_required=False,
            facts=self._build_facts(
                parsed_query=parsed_query,
                products=[],
            ),
            errors=parsed_query.errors,
            source_references=[],
        )

    def _query_products(
        self,
        parsed_query: ParsedQualityQuery,
    ) -> list[Any]:
        """Query products by parsed product reference."""

        reference_type = parsed_query.product_reference_type
        reference_value = parsed_query.product_reference_value

        if reference_type is None or reference_value is None:
            return []

        if reference_type == "sku_id":
            product = self._product_repository.get_by_sku_id(reference_value)
            return [] if product is None else [product]

        if reference_type == "oem_reference_number":
            product = self._product_repository.get_by_oem_reference(
                reference_value,
            )
            return [] if product is None else [product]

        if reference_type == "thread_spec":
            return list(
                self._product_repository.list_by_thread_spec(reference_value),
            )

        return []

    def _resolve_status(
        self,
        *,
        parsed_query: ParsedQualityQuery,
        products: list[Any],
    ) -> tuple[HandlerStatus, bool]:
        """Resolve handler status and handoff flag."""

        query_type = parsed_query.quality_query_type

        if query_type == "material":
            if self._all_products_have_field(products, "material"):
                return "success", False
            return "handoff", True

        if query_type == "surface_treatment":
            if self._all_products_have_field(products, "surface_treatment"):
                return "success", False
            return "handoff", True

        return "handoff", True

    def _build_facts(
        self,
        *,
        parsed_query: ParsedQualityQuery,
        products: list[Any],
    ) -> dict[str, object]:
        """Build quality handler facts without quality commitments."""

        query_type = parsed_query.quality_query_type

        material_available = bool(products) and self._all_products_have_field(
            products,
            "material",
        )
        surface_treatment_available = (
            bool(products)
            and self._all_products_have_field(
                products,
                "surface_treatment",
            )
        )

        return {
            "raw_text": parsed_query.raw_text,
            "is_quality_intent": parsed_query.is_quality_intent,
            "quality_query_type": query_type,
            "product_reference_type": parsed_query.product_reference_type,
            "product_reference_value": parsed_query.product_reference_value,
            "sku_ids": parsed_query.sku_ids,
            "oem_reference_numbers": parsed_query.oem_reference_numbers,
            "thread_specs": parsed_query.thread_specs,
            "products": [
                self._product_to_fact(product)
                for product in products
            ],
            "material_available": material_available,
            "surface_treatment_available": surface_treatment_available,
            "quality_commitment_made": False,
            "durability_committed": False,
            "rust_resistance_committed": False,
            "scratch_resistance_committed": False,
            "fitment_committed": False,
            "defect_judgement_made": False,
            "warranty_committed": False,
            "return_exchange_committed": False,
            "compensation_committed": False,
        }

    @staticmethod
    def _all_products_have_field(
        products: list[Any],
        field_name: str,
    ) -> bool:
        """Return whether all matched products have a non-empty field."""

        return all(
            getattr(product, field_name, None) not in (None, "")
            for product in products
        )

    @staticmethod
    def _product_to_fact(product: Any) -> dict[str, object]:
        """Convert product ORM object to quality-safe facts."""

        return {
            "sku_id": product.sku_id,
            "product_name": product.product_name,
            "thread_spec": product.thread_spec,
            "oem_reference_number": product.oem_reference_number,
            "material": product.material,
            "surface_treatment": product.surface_treatment,
        }

    @staticmethod
    def _build_source_references(
        products: list[Any],
    ) -> list[SourceReference]:
        """Build source references for matched product facts."""

        return [
            SourceReference(
                source_type="database_table",
                source_name="products",
                reference_id=product.sku_id,
            )
            for product in products
        ]