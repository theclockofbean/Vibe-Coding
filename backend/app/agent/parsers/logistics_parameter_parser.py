"""Deterministic parameter parser for logistics queries.

This parser only extracts logistics intent and parameters from text.

It does not query the database, call an LLM, calculate shipping fees,
promise delivery time, promise free shipping, or write data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, TypeAlias


LogisticsParseStatus: TypeAlias = Literal[
    "parsed",
    "not_logistics_intent",
    "missing_product_reference",
    "ambiguous",
]

LogisticsQueryType: TypeAlias = Literal[
    "shipping_time",
    "stock_status",
    "shipping_fee",
    "free_shipping",
    "delivery_time",
    "carrier",
    "tracking",
    "expedite",
]

ProductReferenceType: TypeAlias = Literal[
    "sku_id",
    "sku_ids",
    "oem_reference_number",
    "thread_spec",
]


SKU_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])SKU\s*0*(\d{1,3})(?![A-Za-z0-9])",
    re.IGNORECASE,
)

OEM_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)\d{5}-\d{5}(?!\d)",
)

THREAD_SPEC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])M\s*(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

QUANTITY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])(\d{1,6})\s*(个|件|只|套|pcs)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

DESTINATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"(?:发到|寄到|送到|到)(?P<destination>[\u4e00-\u9fff]{2,16}?)"
        r"(?=几天|多久|什么时候|运费|邮费|物流费|快递费|多少|吗|能发|发货|$)"
    ),
    re.compile(
        r"(?:发(?!货|什么)|寄)(?P<destination>[\u4e00-\u9fff]{2,16}?)"
        r"(?=运费|邮费|物流费|快递费|多少|能发|吗|$)"
    ),
    re.compile(
        r"(?P<destination>[\u4e00-\u9fff]{2,8})能发吗"
    ),
)

LOGISTICS_KEYWORD_GROUPS: Final[
    tuple[tuple[LogisticsQueryType, tuple[str, ...]], ...]
] = (
    (
        "tracking",
        (
            "物流单号",
            "快递单号",
            "查物流",
            "物流信息",
            "快递信息",
        ),
    ),
    (
        "expedite",
        (
            "加急",
            "急用",
            "能快点发吗",
            "今天能发吗",
            "马上发",
            "优先发",
        ),
    ),
    (
        "free_shipping",
        (
            "包邮",
            "免运费",
            "免邮",
            "包不包邮",
            "能包邮吗",
        ),
    ),
    (
        "shipping_fee",
        (
            "运费",
            "邮费",
            "物流费",
            "发货费用",
            "配送费",
            "快递费",
        ),
    ),
    (
        "delivery_time",
        (
            "几天到",
            "多久到",
            "什么时候到",
            "到货时间",
            "几天送到",
            "多久送到",
            "发到杭州几天",
            "寄到上海多久",
        ),
    ),
    (
        "carrier",
        (
            "发什么快递",
            "什么快递",
            "顺丰",
            "圆通",
            "中通",
            "申通",
            "韵达",
            "德邦",
            "物流公司",
            "快递公司",
        ),
    ),
    (
        "stock_status",
        (
            "有现货吗",
            "有没有现货",
            "现货",
            "有没有货",
            "有货吗",
            "库存",
            "备货",
        ),
    ),
    (
        "shipping_time",
        (
            "几天发货",
            "多久发货",
            "什么时候发",
            "发货周期",
            "发货时间",
            "几天能发",
            "什么时候能发",
            "多久能发",
            "能发吗",
        ),
    ),
)


@dataclass(frozen=True)
class ParsedLogisticsQuery:
    """Parsed result for a logistics query."""

    status: LogisticsParseStatus
    raw_text: str
    is_logistics_intent: bool
    logistics_query_type: LogisticsQueryType | None = None
    product_reference_type: ProductReferenceType | None = None
    product_reference_value: str | None = None
    sku_ids: list[str] = field(default_factory=list)
    quantity: int | None = None
    destination_text: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return {
            "status": self.status,
            "raw_text": self.raw_text,
            "is_logistics_intent": self.is_logistics_intent,
            "logistics_query_type": self.logistics_query_type,
            "product_reference_type": self.product_reference_type,
            "product_reference_value": self.product_reference_value,
            "sku_ids": self.sku_ids,
            "quantity": self.quantity,
            "destination_text": self.destination_text,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class LogisticsParameterParser:
    """Parse logistics intent and parameters from user text."""

    def parse(self, text: str) -> ParsedLogisticsQuery:
        """Parse one user text into a structured logistics query."""

        normalized_text = text.strip()

        if not normalized_text:
            return ParsedLogisticsQuery(
                status="not_logistics_intent",
                raw_text=text,
                is_logistics_intent=False,
                errors=["text must not be blank"],
            )

        logistics_query_type = self.extract_logistics_query_type(normalized_text)

        if logistics_query_type is None:
            return ParsedLogisticsQuery(
                status="not_logistics_intent",
                raw_text=text,
                is_logistics_intent=False,
            )

        sku_ids = self.extract_sku_ids(normalized_text)
        oem_reference_numbers = self.extract_oem_reference_numbers(normalized_text)
        thread_specs = self.extract_thread_specs(normalized_text)
        quantity = self.extract_quantity(normalized_text)
        destination_text = self.extract_destination_text(normalized_text)

        if len(sku_ids) > 1:
            return ParsedLogisticsQuery(
                status="ambiguous",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                sku_ids=sku_ids,
                quantity=quantity,
                destination_text=destination_text,
                errors=["multiple SKU IDs found in logistics query"],
            )

        if len(oem_reference_numbers) > 1:
            return ParsedLogisticsQuery(
                status="ambiguous",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                quantity=quantity,
                destination_text=destination_text,
                errors=["multiple OEM reference numbers found"],
            )

        if len(thread_specs) > 1:
            return ParsedLogisticsQuery(
                status="ambiguous",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                quantity=quantity,
                destination_text=destination_text,
                errors=["multiple thread specs found"],
            )

        if self.has_multiple_destination_hint(destination_text):
            return ParsedLogisticsQuery(
                status="ambiguous",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                sku_ids=sku_ids,
                quantity=quantity,
                destination_text=destination_text,
                errors=["multiple destinations found in logistics query"],
            )

        warnings = self._build_priority_warnings(
            has_sku=bool(sku_ids),
            has_oem=bool(oem_reference_numbers),
            has_thread=bool(thread_specs),
        )

        if sku_ids:
            return ParsedLogisticsQuery(
                status="parsed",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                product_reference_type="sku_id",
                product_reference_value=sku_ids[0],
                sku_ids=sku_ids,
                quantity=quantity,
                destination_text=destination_text,
                warnings=warnings,
            )

        if oem_reference_numbers:
            return ParsedLogisticsQuery(
                status="parsed",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                product_reference_type="oem_reference_number",
                product_reference_value=oem_reference_numbers[0],
                quantity=quantity,
                destination_text=destination_text,
                warnings=warnings,
            )

        if thread_specs:
            return ParsedLogisticsQuery(
                status="parsed",
                raw_text=text,
                is_logistics_intent=True,
                logistics_query_type=logistics_query_type,
                product_reference_type="thread_spec",
                product_reference_value=thread_specs[0],
                quantity=quantity,
                destination_text=destination_text,
                warnings=warnings,
            )

        return ParsedLogisticsQuery(
            status="missing_product_reference",
            raw_text=text,
            is_logistics_intent=True,
            logistics_query_type=logistics_query_type,
            quantity=quantity,
            destination_text=destination_text,
            errors=["missing product reference"],
        )

    @staticmethod
    def extract_logistics_query_type(
        text: str,
    ) -> LogisticsQueryType | None:
        """Extract logistics query type by deterministic keyword priority."""

        for query_type, keywords in LOGISTICS_KEYWORD_GROUPS:
            if any(keyword in text for keyword in keywords):
                return query_type

            if query_type == "delivery_time" and (
                (
                    "发到" in text
                    or "寄到" in text
                    or "送到" in text
                    or "到" in text
                )
                and ("几天" in text or "多久" in text or "什么时候" in text)
            ):
                return "delivery_time"

        return None

    @staticmethod
    def extract_sku_ids(text: str) -> list[str]:
        """Extract normalized SKU IDs."""

        sku_ids: list[str] = []

        for match in SKU_PATTERN.finditer(text):
            raw_number = match.group(1)

            try:
                sku_number = int(raw_number)
            except ValueError:
                continue

            if sku_number <= 0:
                continue

            sku_id = f"SKU{sku_number:03d}"

            if sku_id not in sku_ids:
                sku_ids.append(sku_id)

        return sku_ids

    @staticmethod
    def extract_oem_reference_numbers(text: str) -> list[str]:
        """Extract OEM reference numbers."""

        values: list[str] = []

        for match in OEM_PATTERN.finditer(text):
            value = match.group(0)

            if value not in values:
                values.append(value)

        return values

    @classmethod
    def extract_thread_specs(cls, text: str) -> list[str]:
        """Extract and normalize thread specs."""

        values: list[str] = []

        for match in THREAD_SPEC_PATTERN.finditer(text):
            diameter = cls._normalize_decimal_text(match.group(1))
            pitch = cls._normalize_decimal_text(match.group(2))
            value = f"M{diameter}×{pitch}"

            if value not in values:
                values.append(value)

        return values

    @staticmethod
    def extract_quantity(text: str) -> int | None:
        """Extract Arabic numeric quantity."""

        match = QUANTITY_PATTERN.search(text)

        if match is None:
            return None

        quantity = int(match.group(1))

        if quantity <= 0:
            return None

        return quantity

    @staticmethod
    def extract_destination_text(text: str) -> str | None:
        """Extract simple destination text without address validation."""

        for pattern in DESTINATION_PATTERNS:
            match = pattern.search(text)

            if match is None:
                continue

            destination = match.group("destination").strip()

            if destination and destination not in {"什么快递", "货周期"}:
                return destination

        return None

    @staticmethod
    def has_multiple_destination_hint(destination_text: str | None) -> bool:
        """Return whether destination text appears to contain multiple places."""

        if destination_text is None:
            return False

        separators = (
            "和",
            "、",
            "，",
            ",",
            "以及",
        )

        return any(separator in destination_text for separator in separators)

    @staticmethod
    def _normalize_decimal_text(value: str) -> str:
        """Normalize decimal text without scientific notation."""

        try:
            decimal_value = Decimal(value)
        except InvalidOperation:
            return value

        return format(decimal_value.normalize(), "f")

    @staticmethod
    def _build_priority_warnings(
        *,
        has_sku: bool,
        has_oem: bool,
        has_thread: bool,
    ) -> list[str]:
        """Build warnings for product reference priority."""

        warnings: list[str] = []

        if has_sku and has_oem:
            warnings.append("SKU ID has priority over OEM reference number")

        if has_sku and has_thread:
            warnings.append("SKU ID has priority over thread spec")

        if has_oem and has_thread and not has_sku:
            warnings.append("OEM reference number has priority over thread spec")

        return warnings