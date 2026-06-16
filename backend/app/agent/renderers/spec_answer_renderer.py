"""Controlled renderer for specification handler results.

This renderer converts structured specification facts into customer-facing text.
It does not call an LLM and does not invent product facts.
"""

from __future__ import annotations

from typing import Any

from app.agent.handlers import SpecHandlerResult
from app.agent.types import RenderedAnswer


class SpecAnswerRenderer:
    """Render specification handler results into controlled text."""

    def render(self, handler_result: SpecHandlerResult) -> RenderedAnswer:
        """Render one specification handler result."""

        if handler_result.status == "invalid_request":
            return self._render_invalid_request(handler_result)

        if handler_result.status == "not_found":
            return self._render_not_found(handler_result)

        if handler_result.status == "success":
            return self._render_success(handler_result)

        return RenderedAnswer(
            text="当前规格查询结果状态异常，请转人工确认。",
            handoff_required=True,
            source_references=handler_result.source_references,
        )

    def _render_success(
        self,
        handler_result: SpecHandlerResult,
    ) -> RenderedAnswer:
        """Render successful product matches."""

        facts = self._require_facts(handler_result)
        products = self._extract_products(facts)

        if not products:
            return RenderedAnswer(
                text="当前没有查到可展示的产品规格，请转人工确认。",
                handoff_required=True,
                source_references=handler_result.source_references,
            )

        query_type = str(facts.get("query_type") or "")

        if query_type == "product_name_keyword":
            query_value = str(facts.get("query_value") or "")
            text = self._render_product_name_keyword(products, query_value)
        elif len(products) == 1:
            text = self._render_single_product(products[0])
        else:
            text = self._render_multiple_products(products)

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    def _render_not_found(
        self,
        handler_result: SpecHandlerResult,
    ) -> RenderedAnswer:
        """Render no-match result."""

        query_value = self._extract_query_value(handler_result)

        if query_value:
            text = (
                f"没有在当前产品资料中查到“{query_value}”对应的规格记录。"
                "建议核对 SKU、螺纹规格或 OEM 号后再查询。"
            )
        else:
            text = (
                "没有在当前产品资料中查到对应的规格记录。"
                "建议核对 SKU、螺纹规格或 OEM 号后再查询。"
            )

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    def _render_invalid_request(
        self,
        handler_result: SpecHandlerResult,
    ) -> RenderedAnswer:
        """Render invalid structured request."""

        error_text = "；".join(handler_result.errors)

        if error_text:
            text = f"规格查询参数不完整或格式不正确：{error_text}。"
        else:
            text = "规格查询参数不完整或格式不正确。"

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    @staticmethod
    def _render_single_product(product: dict[str, Any]) -> str:
        """Render one product fact dictionary."""

        taper_text = product.get("taper_ratio") or "无锥度"

        return (
            f"查到 {product['sku_id']}：{product['product_name']}。"
            f"螺纹规格为 {product['thread_spec']}，"
            f"杆长 {product['rod_length_mm']} mm，"
            f"球径 {product['ball_diameter_mm']} mm，"
            f"锥度为 {taper_text}。"
            f"材质为 {product['material']}，"
            f"表面处理为 {product['surface_treatment']}。"
            f"OEM 对照号为 {product['oem_reference_number']}。"
            f"起订量 {product['min_order_qty']} 个，"
            f"备货状态为{product['stock_status']}，"
            f"发货周期约 {product['lead_time_days']} 天。"
        )

    @staticmethod
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

        return "\n".join(lines)

    @staticmethod
    def _render_multiple_products(products: list[dict[str, Any]]) -> str:
        """Render multiple product fact dictionaries."""

        lines = [
            f"共查到 {len(products)} 个匹配产品：",
        ]

        for product in products:
            taper_text = product.get("taper_ratio") or "无锥度"
            lines.append(
                "- "
                f"{product['sku_id']}｜{product['product_name']}｜"
                f"{product['thread_spec']}｜"
                f"杆长 {product['rod_length_mm']} mm｜"
                f"球径 {product['ball_diameter_mm']} mm｜"
                f"锥度 {taper_text}｜"
                f"现货状态：{product['stock_status']}｜"
                f"发货周期约 {product['lead_time_days']} 天"
            )

        return "\n".join(lines)

    @staticmethod
    def _require_facts(
        handler_result: SpecHandlerResult,
    ) -> dict[str, object]:
        """Return facts dict or an empty structure."""

        if handler_result.facts is None:
            return {}

        return handler_result.facts

    @staticmethod
    def _extract_products(
        facts: dict[str, object],
    ) -> list[dict[str, Any]]:
        """Extract product dictionaries from handler facts."""

        raw_products = facts.get("products")

        if not isinstance(raw_products, list):
            return []

        products: list[dict[str, Any]] = []

        for raw_product in raw_products:
            if isinstance(raw_product, dict):
                products.append(raw_product)

        return products

    @staticmethod
    def _extract_query_value(
        handler_result: SpecHandlerResult,
    ) -> str:
        """Extract query value from handler facts."""

        if handler_result.facts is None:
            return ""

        query_value = handler_result.facts.get("query_value")

        if not isinstance(query_value, str):
            return ""

        return query_value