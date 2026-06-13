"""Logistics intent handler.

This handler receives ParsedLogisticsQuery and converts it into a unified
HandlerResult.

It may read product facts from the products table, but it does not generate
customer-facing text, call an LLM, promise delivery time, calculate shipping
fees, promise free shipping, promise carriers, or write data.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from app.agent.parsers import ParsedLogisticsQuery
from app.agent.types import HandlerResult, HandlerStatus, SourceReference
from app.repositories import ProductRepository

LogisticsHandlerResult: TypeAlias = HandlerResult


AUTO_SUCCESS_QUERY_TYPES = {
    "shipping_time",
    "stock_status",
}

HANDOFF_QUERY_TYPES = {
    "shipping_fee",
    "free_shipping",
    "delivery_time",
    "carrier",
    "tracking",
    "expedite",
}


class LogisticsHandler:
    """Handle structured logistics queries."""

    handler_name = "logistics_handler"
    primary_intent = "logistics"

    def __init__(
        self,
        *,
        product_repository: ProductRepository,
    ) -> None:
        """Initialize handler with product repository."""

        self._product_repository = product_repository

    def handle(self, parsed_query: ParsedLogisticsQuery) -> HandlerResult:
        """Handle one parsed logistics query."""

        if parsed_query.status == "parsed":
            return self._handle_parsed(parsed_query)

        if parsed_query.status == "missing_product_reference":
            return self._missing_reference_result(parsed_query)

        if parsed_query.status == "ambiguous":
            return self._invalid_request_result(parsed_query)

        if parsed_query.status == "not_logistics_intent":
            return self._invalid_request_result(parsed_query)

        return HandlerResult(
            primary_intent=self.primary_intent,
            handler_name=self.handler_name,
            status="failed",
            matched_count=0,
            handoff_required=True,
            facts=None,
            errors=["unsupported logistics parse status"],
            source_references=[],
        )

    def _handle_parsed(
        self,
        parsed_query: ParsedLogisticsQuery,
    ) -> HandlerResult:
        """Handle parsed logistics query with product reference."""

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

        query_type = parsed_query.logistics_query_type

        if query_type in AUTO_SUCCESS_QUERY_TYPES:
            status: HandlerStatus = "success"
            handoff_required = False
        else:
            status = "handoff"
            handoff_required = True

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
        parsed_query: ParsedLogisticsQuery,
    ) -> HandlerResult:
        """Return handoff result when logistics intent lacks product reference."""

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
        parsed_query: ParsedLogisticsQuery,
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
        parsed_query: ParsedLogisticsQuery,
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

    def _build_facts(
        self,
        *,
        parsed_query: ParsedLogisticsQuery,
        products: list[Any],
    ) -> dict[str, object]:
        """Build logistics handler facts without customer-facing promises."""

        query_type = parsed_query.logistics_query_type

        return {
            "raw_text": parsed_query.raw_text,
            "is_logistics_intent": parsed_query.is_logistics_intent,
            "logistics_query_type": query_type,
            "product_reference_type": parsed_query.product_reference_type,
            "product_reference_value": parsed_query.product_reference_value,
            "sku_ids": parsed_query.sku_ids,
            "quantity": parsed_query.quantity,
            "destination_text": parsed_query.destination_text,
            "products": [
                self._product_to_fact(product)
                for product in products
            ],
            "time_type": (
                "shipping_time_only"
                if query_type == "shipping_time"
                else None
            ),
            "shipping_time_available": (
                query_type == "shipping_time"
                and bool(products)
            ),
            "stock_status_available": (
                query_type == "stock_status"
                and bool(products)
            ),
            "delivery_time_committed": False,
            "shipping_fee_committed": False,
            "free_shipping_committed": False,
            "carrier_committed": False,
            "expedite_committed": False,
            "tracking_supported": False,
        }

    @staticmethod
    def _product_to_fact(product: Any) -> dict[str, object]:
        """Convert product ORM object to logistics-safe facts."""

        return {
            "sku_id": product.sku_id,
            "product_name": product.product_name,
            "thread_spec": product.thread_spec,
            "oem_reference_number": product.oem_reference_number,
            "stock_status": product.stock_status,
            "lead_time_days": product.lead_time_days,
            "min_order_qty": product.min_order_qty,
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