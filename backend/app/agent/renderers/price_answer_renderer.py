"""Controlled renderer for price handler results.

This renderer converts price handler results into customer-facing text.
It does not generate prices, discounts, shipping promises, or quotes.
"""

from __future__ import annotations

from app.agent.types import HandlerResult, RenderedAnswer


class PriceAnswerRenderer:
    """Render price handler results into controlled text."""

    def render(self, handler_result: HandlerResult) -> RenderedAnswer:
        """Render one price handler result."""

        if handler_result.status == "handoff":
            return self._render_handoff(handler_result)

        if handler_result.status == "invalid_request":
            return self._render_invalid_request(handler_result)

        return RenderedAnswer(
            text="当前价格查询状态异常，请转人工确认。",
            handoff_required=True,
            source_references=handler_result.source_references,
        )

    def _render_handoff(
        self,
        handler_result: HandlerResult,
    ) -> RenderedAnswer:
        """Render handoff result for price queries."""

        facts = self._get_facts(handler_result)
        price_query_type = self._get_text_fact(facts, "price_query_type")
        reference_text = self._build_reference_text(facts)
        quantity_text = self._build_quantity_text(facts)

        if price_query_type == "shipping_fee":
            text = self._render_shipping_fee_handoff(
                reference_text=reference_text,
                quantity_text=quantity_text,
            )
        elif reference_text:
            text = (
                f"这类问题涉及报价。{reference_text}{quantity_text}"
                "当前系统尚未接入正式价格表，不能直接给出报价。"
                "请补充采购数量、定制要求和收货地区后转人工确认。"
            )
        else:
            text = (
                "这类问题涉及报价。请先提供 SKU、OEM 对照号或螺纹规格，"
                "以及预计采购数量。当前系统尚未接入正式价格表，不能直接给出报价，"
                "需要转人工确认。"
            )

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    def _render_invalid_request(
        self,
        handler_result: HandlerResult,
    ) -> RenderedAnswer:
        """Render invalid price request."""

        facts = self._get_facts(handler_result)
        is_price_intent = facts.get("is_price_intent")

        if is_price_intent is False:
            text = "当前未识别为价格问题，未进入报价处理。"
        else:
            error_text = "；".join(handler_result.errors)

            if "multiple SKU IDs found in price query" in error_text:
                text = "识别到多个 SKU，请一次只询问一个 SKU 的报价信息。"
            elif "multiple OEM reference numbers found" in error_text:
                text = "识别到多个 OEM 对照号，请一次只询问一个产品的报价信息。"
            elif "multiple thread specs found" in error_text:
                text = "识别到多个螺纹规格，请一次只询问一个规格的报价信息。"
            elif error_text:
                text = f"当前价格查询参数不明确：{error_text}。"
            else:
                text = "当前未识别为价格问题，未进入报价处理。"

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    @staticmethod
    def _render_shipping_fee_handoff(
        *,
        reference_text: str,
        quantity_text: str,
    ) -> str:
        """Render shipping-fee-related handoff text."""

        if reference_text:
            return (
                f"这类问题涉及物流费用或免运条件。{reference_text}{quantity_text}"
                "需要结合收货地区、采购数量和发货方式确认。"
                "当前系统不能自动承诺物流费用，请转人工确认。"
            )

        return (
            "这类问题涉及物流费用或免运条件。请先提供 SKU、OEM 对照号或螺纹规格，"
            "并补充采购数量和收货地区。当前系统不能自动承诺物流费用，"
            "请转人工确认。"
        )

    @staticmethod
    def _get_facts(handler_result: HandlerResult) -> dict[str, object]:
        """Return facts dict or an empty dict."""

        if handler_result.facts is None:
            return {}

        return handler_result.facts

    @staticmethod
    def _get_text_fact(
        facts: dict[str, object],
        key: str,
    ) -> str:
        """Read a string fact safely."""

        value = facts.get(key)

        if not isinstance(value, str):
            return ""

        return value

    @classmethod
    def _build_reference_text(cls, facts: dict[str, object]) -> str:
        """Build product reference text without querying product data."""

        reference_type = cls._get_text_fact(facts, "product_reference_type")
        reference_value = cls._get_text_fact(facts, "product_reference_value")

        if not reference_type or not reference_value:
            return ""

        if reference_type == "sku_id":
            return f"已识别到 SKU：{reference_value}。"

        if reference_type == "oem_reference_number":
            return f"已识别到 OEM 对照号：{reference_value}。"

        if reference_type == "thread_spec":
            return f"已识别到螺纹规格：{reference_value}。"

        return ""

    @staticmethod
    def _build_quantity_text(facts: dict[str, object]) -> str:
        """Build quantity text."""

        quantity = facts.get("quantity")

        if not isinstance(quantity, int):
            return ""

        return f"已识别到采购数量：{quantity}。"