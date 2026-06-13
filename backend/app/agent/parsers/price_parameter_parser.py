"""Rule-based parser for price query parameters.

This parser identifies price-related intent and extracts deterministic
parameters from simple customer text.

It does not call an LLM, query the database, or generate prices.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, TypeAlias

PriceParseStatus: TypeAlias = Literal[
    "parsed",
    "not_price_intent",
    "missing_product_reference",
    "ambiguous",
]

PriceQueryType: TypeAlias = Literal[
    "general_price",
    "unit_price",
    "bulk_price",
    "discount",
    "lowest_price",
    "shipping_fee",
]

ProductReferenceType: TypeAlias = Literal[
    "sku_id",
    "sku_ids",
    "oem_reference_number",
    "thread_spec",
]


SKU_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bSKU[-_\s]?(?P<number>\d{1,3})\b",
    re.IGNORECASE,
)

OEM_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?P<oem>\d{5}-\d{5})\b",
)

THREAD_SPEC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bM\s*(?P<diameter>\d+(?:\.\d+)?)\s*[×xX*＊]\s*"
    r"(?P<pitch>\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)

QUANTITY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<quantity>[1-9]\d{0,6})\s*(?:个|件|只|套|pcs|pc)",
    re.IGNORECASE,
)

PRICE_KEYWORD_GROUPS: Final[
    tuple[tuple[PriceQueryType, tuple[str, ...]], ...]
] = (
    (
        "shipping_fee",
        (
            "运费",
            "包邮",
            "邮费",
            "发货费用",
            "物流费",
        ),
    ),
    (
        "lowest_price",
        (
            "最低价",
            "底价",
            "最便宜",
            "最低多少",
        ),
    ),
    (
        "discount",
        (
            "优惠",
            "折扣",
            "便宜点",
            "活动价",
            "促销",
        ),
    ),
    (
        "bulk_price",
        (
            "批发价",
            "拿货价",
            "批量",
            "大量",
            "一箱",
            "整箱",
        ),
    ),
    (
        "unit_price",
        (
            "单价",
            "多少一个",
            "多少一件",
            "一个多少钱",
            "一件多少钱",
        ),
    ),
    (
        "general_price",
        (
            "多少钱",
            "价格",
            "报价",
            "怎么卖",
            "多少",
            "卖多少",
            "费用",
        ),
    ),
)


@dataclass(frozen=True)
class ParsedPriceQuery:
    """Parsed price query parameters."""

    status: PriceParseStatus
    raw_text: str
    is_price_intent: bool
    price_query_type: PriceQueryType | None = None
    product_reference_type: ProductReferenceType | None = None
    product_reference_value: str | None = None
    sku_ids: list[str] = field(default_factory=list)
    quantity: int | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)


class PriceParameterParser:
    """Extract price query intent and parameters from customer text."""

    def parse(self, text: str) -> ParsedPriceQuery:
        """Parse customer text into structured price query parameters."""

        raw_text = text
        normalized_text = text.strip()

        if not normalized_text:
            return ParsedPriceQuery(
                status="not_price_intent",
                raw_text=raw_text,
                is_price_intent=False,
                errors=["text must not be blank"],
            )

        price_query_type = self.extract_price_query_type(normalized_text)

        if price_query_type is None:
            return ParsedPriceQuery(
                status="not_price_intent",
                raw_text=raw_text,
                is_price_intent=False,
            )

        quantity = self.extract_quantity(normalized_text)
        sku_ids = self.extract_sku_ids(normalized_text)
        oem_numbers = self.extract_oem_reference_numbers(normalized_text)
        thread_specs = self.extract_thread_specs(normalized_text)

        if len(sku_ids) > 1:
            return ParsedPriceQuery(
                status="ambiguous",
                raw_text=raw_text,
                is_price_intent=True,
                price_query_type=price_query_type,
                sku_ids=sku_ids,
                quantity=quantity,
                errors=["multiple SKU IDs found in price query"],
            )

        warnings = self._build_priority_warnings(
            sku_ids=sku_ids,
            oem_numbers=oem_numbers,
            thread_specs=thread_specs,
        )

        if sku_ids:
            return ParsedPriceQuery(
                status="parsed",
                raw_text=raw_text,
                is_price_intent=True,
                price_query_type=price_query_type,
                product_reference_type="sku_id",
                product_reference_value=sku_ids[0],
                sku_ids=sku_ids,
                quantity=quantity,
                warnings=warnings,
            )

        if oem_numbers:
            if len(oem_numbers) > 1:
                return ParsedPriceQuery(
                    status="ambiguous",
                    raw_text=raw_text,
                    is_price_intent=True,
                    price_query_type=price_query_type,
                    quantity=quantity,
                    errors=["multiple OEM reference numbers found"],
                )

            return ParsedPriceQuery(
                status="parsed",
                raw_text=raw_text,
                is_price_intent=True,
                price_query_type=price_query_type,
                product_reference_type="oem_reference_number",
                product_reference_value=oem_numbers[0],
                quantity=quantity,
                warnings=warnings,
            )

        if thread_specs:
            if len(thread_specs) > 1:
                return ParsedPriceQuery(
                    status="ambiguous",
                    raw_text=raw_text,
                    is_price_intent=True,
                    price_query_type=price_query_type,
                    quantity=quantity,
                    errors=["multiple thread specs found"],
                )

            return ParsedPriceQuery(
                status="parsed",
                raw_text=raw_text,
                is_price_intent=True,
                price_query_type=price_query_type,
                product_reference_type="thread_spec",
                product_reference_value=thread_specs[0],
                quantity=quantity,
                warnings=warnings,
            )

        return ParsedPriceQuery(
            status="missing_product_reference",
            raw_text=raw_text,
            is_price_intent=True,
            price_query_type=price_query_type,
            quantity=quantity,
            errors=[
                "price intent found but no SKU ID, OEM reference number, "
                "or thread spec was found"
            ],
        )

    @staticmethod
    def extract_price_query_type(text: str) -> PriceQueryType | None:
        """Extract price query type by deterministic keyword matching."""

        for query_type, keywords in PRICE_KEYWORD_GROUPS:
            if any(keyword in text for keyword in keywords):
                return query_type

        return None

    @staticmethod
    def extract_sku_ids(text: str) -> list[str]:
        """Extract canonical SKU IDs from text."""

        sku_ids: list[str] = []

        for match in SKU_PATTERN.finditer(text):
            number = int(match.group("number"))
            sku_id = f"SKU{number:03d}"

            if sku_id not in sku_ids:
                sku_ids.append(sku_id)

        return sku_ids

    @staticmethod
    def extract_oem_reference_numbers(text: str) -> list[str]:
        """Extract OEM reference numbers from text."""

        oem_numbers: list[str] = []

        for match in OEM_PATTERN.finditer(text):
            oem_number = match.group("oem")

            if oem_number not in oem_numbers:
                oem_numbers.append(oem_number)

        return oem_numbers

    @classmethod
    def extract_thread_specs(cls, text: str) -> list[str]:
        """Extract canonical metric thread specs from text."""

        thread_specs: list[str] = []

        for match in THREAD_SPEC_PATTERN.finditer(text):
            diameter = cls._normalize_decimal_text(match.group("diameter"))
            pitch = cls._normalize_decimal_text(match.group("pitch"))

            if diameter is None or pitch is None:
                continue

            thread_spec = f"M{diameter}×{pitch}"

            if thread_spec not in thread_specs:
                thread_specs.append(thread_spec)

        return thread_specs

    @staticmethod
    def extract_quantity(text: str) -> int | None:
        """Extract simple Arabic-number quantity from text."""

        match = QUANTITY_PATTERN.search(text)

        if match is None:
            return None

        return int(match.group("quantity"))

    @staticmethod
    def _normalize_decimal_text(value: str) -> str | None:
        """Normalize decimal text without scientific notation."""

        try:
            decimal_value = Decimal(value)
        except InvalidOperation:
            return None

        if decimal_value <= 0:
            return None

        normalized = format(decimal_value.normalize(), "f")

        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")

        return normalized

    @staticmethod
    def _build_priority_warnings(
        *,
        sku_ids: list[str],
        oem_numbers: list[str],
        thread_specs: list[str],
    ) -> list[str]:
        """Return warnings when lower-priority identifiers are ignored."""

        warnings: list[str] = []

        if sku_ids and oem_numbers:
            warnings.append("SKU ID has priority over OEM reference number")

        if sku_ids and thread_specs:
            warnings.append("SKU ID has priority over thread spec")

        if oem_numbers and thread_specs and not sku_ids:
            warnings.append("OEM reference number has priority over thread spec")

        return warnings