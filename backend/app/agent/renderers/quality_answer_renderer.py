"""Renderer for quality answers.

This renderer converts HandlerResult into a controlled RenderedAnswer.

It does not query databases, call LLMs, add new product facts, promise
durability, promise rust resistance, promise scratch resistance, promise
warranty, promise returns/exchanges, promise compensation, or judge quality
responsibility.
"""

from __future__ import annotations

from typing import Any

from app.agent.types import HandlerResult, RenderedAnswer


class QualityAnswerRenderer:
    """Render quality handler result into controlled answer text."""

    def render(self, handler_result: HandlerResult) -> RenderedAnswer:
        """Render one quality handler result."""

        if handler_result.status == "success":
            text = self._render_success(handler_result)
        elif handler_result.status == "handoff":
            text = self._render_handoff(handler_result)
        elif handler_result.status == "not_found":
            text = self._render_not_found(handler_result)
        elif handler_result.status == "invalid_request":
            text = self._render_invalid_request(handler_result)
        else:
            text = "质量问题处理失败，请转人工确认。"

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    def _render_success(self, handler_result: HandlerResult) -> str:
        """Render success result."""

        facts = self._facts(handler_result)
        query_type = self._get_text_fact(facts, "quality_query_type")
        product = self._first_product(facts)

        if product is None:
            return "当前未取得可用于回答的产品质量基础信息，请转人工确认。"

        sku_id = self._get_product_text(product, "sku_id")
        product_name = self._get_product_text(product, "product_name")

        if query_type == "material":
            material = self._get_product_text(product, "material")
            return (
                f"查到 {sku_id}：{product_name}。"
                f"该产品登记材质为{material}。"
                "该回答仅基于当前已登记的产品信息，不代表额外质量承诺。"
            )

        if query_type == "surface_treatment":
            surface_treatment = self._get_product_text(
                product,
                "surface_treatment",
            )
            return (
                f"查到 {sku_id}：{product_name}。"
                f"该产品登记表面处理为{surface_treatment}。"
                "该回答仅基于当前已登记的产品信息，"
                "不代表防锈、耐刮或不掉漆承诺。"
            )

        return "当前质量问题不属于可自动回答范围，请转人工进一步确认。"

    def _render_handoff(self, handler_result: HandlerResult) -> str:
        """Render handoff result."""

        facts = self._facts(handler_result)
        query_type = self._get_text_fact(facts, "quality_query_type")
        product_reference_value = self._get_text_fact(
            facts,
            "product_reference_value",
        )
        product = self._first_product(facts)

        if product_reference_value == "":
            return (
                "这是质量相关问题，但当前缺少产品引用。"
                "请先提供 SKU、OEM 对照号或螺纹规格；"
                "如涉及质保、退换、赔付或质量责任，请转人工确认。"
            )

        if product is None:
            return "当前质量问题需要人工进一步确认。"

        sku_id = self._get_product_text(product, "sku_id")
        product_name = self._get_product_text(product, "product_name")

        if query_type == "material":
            return (
                f"已匹配到 {sku_id}：{product_name}，"
                "但当前系统未登记该产品材质信息。请转人工进一步确认。"
            )

        if query_type == "surface_treatment":
            return (
                f"已匹配到 {sku_id}：{product_name}，"
                "但当前系统未登记该产品表面处理信息。请转人工进一步确认。"
            )

        if query_type == "durability":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前系统不能自动承诺产品寿命、耐用年限或长期使用结果，"
                "该问题需要结合使用环境、安装方式和实际工况确认。"
                "请转人工进一步确认。"
            )

        if query_type == "rust_resistance":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前系统不能自动承诺不生锈或绝对防锈；"
                "如需确认防锈表现，需要结合材质、表面处理、使用环境和维护方式。"
                "请转人工进一步确认。"
            )

        if query_type == "scratch_resistance":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前系统不能自动承诺不掉漆、耐刮等级或不磨损；"
                "该问题需要结合表面处理、使用环境和实际接触情况确认。"
                "请转人工进一步确认。"
            )

        if query_type == "fitment_risk":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前质量模块不能单独承诺适配结果；"
                "请提供车型、年份、原车螺纹或 OEM 信息，由人工进一步确认。"
            )

        if query_type == "defect_issue":
            return (
                f"查到 {sku_id}：{product_name}。"
                "该问题涉及疑似瑕疵或使用异常，当前系统不能直接判断责任，"
                "也不能自动承诺补发、退换或赔付。"
                "请提供订单、图片、视频和安装信息，并转人工处理。"
            )

        if query_type == "warranty":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前系统未接入正式质保规则，不能自动承诺质保期限或保修范围。"
                "请转人工进一步确认。"
            )

        if query_type == "return_exchange":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前系统未接入正式退换货规则，不能自动承诺一定可退或一定可换。"
                "请转人工进一步确认。"
            )

        if query_type == "compensation":
            return (
                f"查到 {sku_id}：{product_name}。"
                "该问题涉及赔付、补偿或补发，当前系统不能自动承诺处理结果。"
                "请提供订单、图片、视频和问题说明，并转人工确认。"
            )

        if query_type == "general_quality":
            return (
                f"查到 {sku_id}：{product_name}。"
                "当前系统不能对产品质量作泛化承诺或主观评价；"
                "如需确认具体质量表现，请转人工进一步确认。"
            )

        return "当前质量问题需要人工进一步确认。"

    def _render_not_found(self, handler_result: HandlerResult) -> str:
        """Render not found result."""

        facts = self._facts(handler_result)
        product_reference_value = self._get_text_fact(
            facts,
            "product_reference_value",
        )

        if product_reference_value == "":
            product_reference_value = "该产品引用"

        return (
            f"暂未查到 {product_reference_value} 对应的质量基础信息。"
            "请核对 SKU、OEM 对照号或螺纹规格；"
            "如仍需确认质量问题，请转人工处理。"
        )

    def _render_invalid_request(self, handler_result: HandlerResult) -> str:
        """Render invalid request result."""

        error_text = "；".join(handler_result.errors)

        if "multiple SKU IDs found in quality query" in error_text:
            return (
                "识别到多个 SKU，当前质量模块一次只能确认一个产品。"
                "请保留一个 SKU 后重新提问。"
            )

        if "multiple OEM reference numbers found in quality query" in error_text:
            return (
                "识别到多个 OEM 对照号，当前质量模块一次只能确认一个产品。"
                "请保留一个 OEM 对照号后重新提问。"
            )

        if "multiple thread specs found in quality query" in error_text:
            return (
                "识别到多个螺纹规格，当前质量模块一次只能确认一个产品范围。"
                "请保留一个螺纹规格后重新提问。"
            )

        return "当前未识别为质量问题，未进入质量处理。"

    @staticmethod
    def _facts(handler_result: HandlerResult) -> dict[str, object]:
        """Return facts dictionary from handler result."""

        if handler_result.facts is None:
            return {}

        return handler_result.facts

    @staticmethod
    def _first_product(facts: dict[str, object]) -> dict[str, object] | None:
        """Return first product fact."""

        products = facts.get("products")

        if not isinstance(products, list) or not products:
            return None

        first_product = products[0]

        if not isinstance(first_product, dict):
            return None

        return first_product

    @staticmethod
    def _get_text_fact(
        facts: dict[str, object],
        key: str,
    ) -> str:
        """Read a text value from facts."""

        value = facts.get(key)

        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _get_product_text(
        product: dict[str, Any],
        key: str,
    ) -> str:
        """Read a text value from product fact."""

        value = product.get(key)

        if value is None:
            return ""

        return str(value)