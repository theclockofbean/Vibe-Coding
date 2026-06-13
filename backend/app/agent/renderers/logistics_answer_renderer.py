"""Controlled renderer for logistics handler results.

This renderer converts logistics handler results into customer-facing text.
It does not query the database, call an LLM, calculate shipping fees, promise
free shipping, promise delivery time, promise carriers, or promise expedite.
"""

from __future__ import annotations

from app.agent.types import HandlerResult, RenderedAnswer


class LogisticsAnswerRenderer:
    """Render logistics handler results into controlled text."""

    def render(self, handler_result: HandlerResult) -> RenderedAnswer:
        """Render one logistics handler result."""

        if handler_result.status == "success":
            return self._render_success(handler_result)

        if handler_result.status == "handoff":
            return self._render_handoff(handler_result)

        if handler_result.status == "not_found":
            return self._render_not_found(handler_result)

        if handler_result.status == "invalid_request":
            return self._render_invalid_request(handler_result)

        return RenderedAnswer(
            text="当前物流查询状态异常，请转人工确认。",
            handoff_required=True,
            source_references=handler_result.source_references,
        )

    def _render_success(
        self,
        handler_result: HandlerResult,
    ) -> RenderedAnswer:
        """Render automatically answerable logistics result."""

        facts = self._get_facts(handler_result)
        query_type = self._get_text_fact(facts, "logistics_query_type")
        products = self._get_products(facts)

        if not products:
            return RenderedAnswer(
                text="当前物流查询缺少产品基础信息，请转人工确认。",
                handoff_required=True,
                source_references=handler_result.source_references,
            )

        product = products[0]

        if query_type == "shipping_time":
            text = self._render_shipping_time_success(product)
        elif query_type == "stock_status":
            text = self._render_stock_status_success(product)
        else:
            text = "当前物流查询需要进一步确认，请转人工处理。"

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    def _render_handoff(
        self,
        handler_result: HandlerResult,
    ) -> RenderedAnswer:
        """Render logistics handoff result."""

        facts = self._get_facts(handler_result)
        query_type = self._get_text_fact(facts, "logistics_query_type")
        product_prefix = self._build_product_prefix(facts)

        if self._get_text_fact(facts, "product_reference_value") == "":
            text = (
                "这类问题涉及物流确认。请先提供 SKU、OEM 对照号或螺纹规格；"
                "如果询问物流费用、免运条件或到货时间，还需要补充收货地区和采购数量。"
            )
        elif query_type == "shipping_fee":
            text = (
                f"{product_prefix}"
                "物流费用需要结合收货地区、采购数量和发货方式确认。"
                "当前系统不能自动承诺具体物流费用，请转人工确认。"
            )
        elif query_type == "free_shipping":
            text = (
                f"{product_prefix}"
                "免运条件需要结合收货地区、采购数量和当前业务政策确认。"
                "当前系统不能自动承诺免运，请转人工确认。"
            )
        elif query_type == "delivery_time":
            destination_prefix = self._build_destination_prefix(facts)
            text = (
                f"{product_prefix}{destination_prefix}"
                "到货时间受收货地区、快递方式和物流揽收影响。"
                "当前系统不能自动承诺具体到货时间，请转人工确认。"
            )
        elif query_type == "carrier":
            text = (
                f"{product_prefix}"
                "快递公司需要结合订单、发货仓和当时发货安排确认。"
                "当前系统不能自动承诺指定快递，请转人工确认。"
            )
        elif query_type == "tracking":
            text = (
                "物流单号需要根据已生成订单或发货记录查询。"
                "当前系统未接入订单物流数据，请转人工确认。"
            )
        elif query_type == "expedite":
            text = (
                f"{product_prefix}"
                "加急发货需要结合库存、订单时间和仓库处理能力确认。"
                "当前系统不能自动承诺加急，请转人工确认。"
            )
        else:
            text = "当前物流问题需要人工进一步确认，请转人工处理。"

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    def _render_not_found(
        self,
        handler_result: HandlerResult,
    ) -> RenderedAnswer:
        """Render product-not-found logistics result."""

        facts = self._get_facts(handler_result)
        reference_value = self._get_text_fact(facts, "product_reference_value")

        if reference_value:
            text = (
                f"暂未查到 {reference_value} 对应的物流基础信息。"
                "请核对 SKU、OEM 对照号或螺纹规格后再确认；"
                "如仍无法确认，请转人工处理。"
            )
        else:
            text = (
                "暂未查到该产品对应的物流基础信息。"
                "请核对 SKU、OEM 对照号或螺纹规格后再确认；"
                "如仍无法确认，请转人工处理。"
            )

        return RenderedAnswer(
            text=text,
            handoff_required=True,
            source_references=handler_result.source_references,
        )

    def _render_invalid_request(
        self,
        handler_result: HandlerResult,
    ) -> RenderedAnswer:
        """Render invalid logistics request."""

        facts = self._get_facts(handler_result)

        if facts.get("is_logistics_intent") is False:
            text = "当前未识别为物流问题，未进入物流处理。"
        else:
            error_text = "；".join(handler_result.errors)

            if "multiple SKU IDs found in logistics query" in error_text:
                text = "识别到多个 SKU，请一次只询问一个产品的物流信息。"
            elif "multiple OEM reference numbers found" in error_text:
                text = "识别到多个 OEM 对照号，请一次只询问一个产品的物流信息。"
            elif "multiple thread specs found" in error_text:
                text = "识别到多个螺纹规格，请一次只询问一个规格的物流信息。"
            elif "multiple destinations found in logistics query" in error_text:
                text = "识别到多个收货地区，请一次只询问一个地区的物流信息。"
            elif error_text:
                text = f"当前物流查询参数不明确：{error_text}。"
            else:
                text = "当前物流查询参数不明确，请补充后再确认。"

        return RenderedAnswer(
            text=text,
            handoff_required=handler_result.handoff_required,
            source_references=handler_result.source_references,
        )

    @staticmethod
    def _render_shipping_time_success(product: dict[str, object]) -> str:
        """Render shipping-time success answer."""

        sku_id = str(product.get("sku_id", ""))
        product_name = str(product.get("product_name", ""))
        stock_status = str(product.get("stock_status", ""))
        lead_time_days = product.get("lead_time_days")

        return (
            f"查到 {sku_id}：{product_name}。"
            f"当前备货状态为{stock_status}，发货周期约 {lead_time_days} 天。"
            "该时间仅表示发货周期，不代表到货时间。"
        )

    @staticmethod
    def _render_stock_status_success(product: dict[str, object]) -> str:
        """Render stock-status success answer."""

        sku_id = str(product.get("sku_id", ""))
        product_name = str(product.get("product_name", ""))
        stock_status = str(product.get("stock_status", ""))

        return f"查到 {sku_id}：{product_name}。当前备货状态为{stock_status}。"

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

    @staticmethod
    def _get_products(
        facts: dict[str, object],
    ) -> list[dict[str, object]]:
        """Read product facts safely."""

        products = facts.get("products")

        if not isinstance(products, list):
            return []

        result: list[dict[str, object]] = []

        for product in products:
            if isinstance(product, dict):
                result.append(product)

        return result

    @classmethod
    def _build_product_prefix(cls, facts: dict[str, object]) -> str:
        """Build controlled product prefix."""

        products = cls._get_products(facts)

        if not products:
            return ""

        if len(products) == 1:
            product = products[0]
            sku_id = str(product.get("sku_id", ""))
            product_name = str(product.get("product_name", ""))

            return f"已识别到 {sku_id}：{product_name}。"

        sku_ids = [
            str(product.get("sku_id", ""))
            for product in products[:3]
            if product.get("sku_id")
        ]

        if not sku_ids:
            return ""

        return f"已匹配到多个产品：{'、'.join(sku_ids)}。请进一步确认具体 SKU。"

    @classmethod
    def _build_destination_prefix(cls, facts: dict[str, object]) -> str:
        """Build controlled destination prefix."""

        destination_text = cls._get_text_fact(facts, "destination_text")

        if not destination_text:
            return ""

        return f"已识别到收货地区：{destination_text}。"