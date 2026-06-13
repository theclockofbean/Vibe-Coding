"""Parameter parser for quality-related product queries.

The parser only identifies quality intent and extracts product references.
It does not query databases, call LLMs, answer quality questions, or make
quality, warranty, return, exchange, compensation, fitment, durability, rust,
or scratch-resistance commitments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

QualityParseStatus = Literal[
    "parsed",
    "not_quality_intent",
    "missing_product_reference",
    "ambiguous",
]

QualityQueryType = Literal[
    "material",
    "surface_treatment",
    "durability",
    "rust_resistance",
    "scratch_resistance",
    "fitment_risk",
    "defect_issue",
    "warranty",
    "return_exchange",
    "compensation",
    "general_quality",
]

ProductReferenceType = Literal[
    "sku_id",
    "oem_reference_number",
    "thread_spec",
]


SKU_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bSKU\d{3,}\b",
    re.IGNORECASE,
)

OEM_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b\d{5}-\d{5}\b",
)

THREAD_SPEC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bM(?P<size>\d{1,2})\s*[xX×*]\s*(?P<pitch>\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)


QUALITY_QUERY_PRIORITY: Final[tuple[QualityQueryType, ...]] = (
    "compensation",
    "return_exchange",
    "warranty",
    "defect_issue",
    "fitment_risk",
    "rust_resistance",
    "scratch_resistance",
    "durability",
    "surface_treatment",
    "material",
    "general_quality",
)


QUALITY_KEYWORDS: Final[dict[QualityQueryType, tuple[str, ...]]] = {
    "material": (
        "材质",
        "材料",
        "什么材质",
        "什么材料",
        "铝合金",
        "不锈钢",
        "碳钢",
        "塑料",
        "金属",
    ),
    "surface_treatment": (
        "表面处理",
        "表面工艺",
        "表面怎么处理",
        "表面如何处理",
        "表面怎样处理",
        "表面是什么工艺",
        "表面工艺是什么",
        "表面",
        "工艺",
        "电镀",
        "喷砂",
        "阳极氧化",
        "氧化",
        "喷漆",
        "镀铬",
        "抛光",
    ),
    "durability": (
        "耐用",
        "寿命",
        "能用多久",
        "能用几年",
        "容易坏",
        "会不会坏",
        "结实",
        "质量怎么样",
        "质量好吗",
        "质量好不好",
    ),
    "rust_resistance": (
        "生锈",
        "防锈",
        "会锈",
        "锈蚀",
        "遇水",
        "腐蚀",
    ),
    "scratch_resistance": (
        "掉漆",
        "掉色",
        "耐刮",
        "划痕",
        "磨花",
        "磨损",
        "刮花",
        "表面容易坏",
    ),
    "fitment_risk": (
        "装不上",
        "不适配",
        "买错",
        "能不能用",
        "适不适合",
        "不合适",
        "车型",
        "年份",
    ),
    "defect_issue": (
        "划痕",
        "破损",
        "坏了",
        "松动",
        "异响",
        "瑕疵",
        "裂了",
        "断了",
        "收到有问题",
    ),
    "warranty": (
        "质保",
        "保修",
        "保多久",
        "坏了保不保",
        "保不保",
    ),
    "return_exchange": (
        "退货",
        "换货",
        "能退",
        "能换",
        "退换",
        "不合适能不能退",
        "不合适能不能换",
    ),
    "compensation": (
        "赔",
        "赔付",
        "补偿",
        "补发",
        "怎么赔",
        "能不能赔",
        "质量问题能赔吗",
    ),
    "general_quality": (
        "质量",
        "品质",
        "做工",
        "好不好",
        "靠谱吗",
        "稳定吗",
        "质量更好",
    ),
}


@dataclass(frozen=True)
class ParsedQualityQuery:
    """Parsed quality query result."""

    raw_text: str
    status: QualityParseStatus
    is_quality_intent: bool
    quality_query_type: QualityQueryType | None
    product_reference_type: ProductReferenceType | None
    product_reference_value: str | None
    sku_ids: list[str]
    oem_reference_numbers: list[str]
    thread_specs: list[str]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return serializable dictionary."""

        return {
            "raw_text": self.raw_text,
            "status": self.status,
            "is_quality_intent": self.is_quality_intent,
            "quality_query_type": self.quality_query_type,
            "product_reference_type": self.product_reference_type,
            "product_reference_value": self.product_reference_value,
            "sku_ids": self.sku_ids,
            "oem_reference_numbers": self.oem_reference_numbers,
            "thread_specs": self.thread_specs,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class QualityParameterParser:
    """Parse quality intent and product references from raw text."""

    def parse(self, raw_text: str) -> ParsedQualityQuery:
        """Parse one raw quality query."""

        normalized_text = raw_text.strip()

        sku_ids = self._extract_sku_ids(normalized_text)
        oem_reference_numbers = self._extract_oem_reference_numbers(
            normalized_text,
        )
        thread_specs = self._extract_thread_specs(normalized_text)
        quality_query_type = self._extract_quality_query_type(normalized_text)

        if quality_query_type is None:
            return ParsedQualityQuery(
                raw_text=raw_text,
                status="not_quality_intent",
                is_quality_intent=False,
                quality_query_type=None,
                product_reference_type=None,
                product_reference_value=None,
                sku_ids=[],
                oem_reference_numbers=[],
                thread_specs=[],
                warnings=[],
                errors=[],
            )

        ambiguous_errors = self._build_ambiguity_errors(
            sku_ids=sku_ids,
            oem_reference_numbers=oem_reference_numbers,
            thread_specs=thread_specs,
        )

        if ambiguous_errors:
            return ParsedQualityQuery(
                raw_text=raw_text,
                status="ambiguous",
                is_quality_intent=True,
                quality_query_type=quality_query_type,
                product_reference_type=None,
                product_reference_value=None,
                sku_ids=sku_ids,
                oem_reference_numbers=oem_reference_numbers,
                thread_specs=thread_specs,
                warnings=[],
                errors=ambiguous_errors,
            )

        product_reference_type = self._resolve_product_reference_type(
            sku_ids=sku_ids,
            oem_reference_numbers=oem_reference_numbers,
            thread_specs=thread_specs,
        )
        product_reference_value = self._resolve_product_reference_value(
            product_reference_type=product_reference_type,
            sku_ids=sku_ids,
            oem_reference_numbers=oem_reference_numbers,
            thread_specs=thread_specs,
        )

        if product_reference_type is None or product_reference_value is None:
            return ParsedQualityQuery(
                raw_text=raw_text,
                status="missing_product_reference",
                is_quality_intent=True,
                quality_query_type=quality_query_type,
                product_reference_type=None,
                product_reference_value=None,
                sku_ids=sku_ids,
                oem_reference_numbers=oem_reference_numbers,
                thread_specs=thread_specs,
                warnings=[],
                errors=["missing product reference"],
            )

        return ParsedQualityQuery(
            raw_text=raw_text,
            status="parsed",
            is_quality_intent=True,
            quality_query_type=quality_query_type,
            product_reference_type=product_reference_type,
            product_reference_value=product_reference_value,
            sku_ids=sku_ids,
            oem_reference_numbers=oem_reference_numbers,
            thread_specs=thread_specs,
            warnings=[],
            errors=[],
        )

    @staticmethod
    def _extract_sku_ids(text: str) -> list[str]:
        """Extract normalized SKU IDs."""

        values = [
            match.group(0).upper()
            for match in SKU_PATTERN.finditer(text)
        ]

        return list(dict.fromkeys(values))

    @staticmethod
    def _extract_oem_reference_numbers(text: str) -> list[str]:
        """Extract OEM reference numbers."""

        values = [
            match.group(0)
            for match in OEM_PATTERN.finditer(text)
        ]

        return list(dict.fromkeys(values))

    @staticmethod
    def _extract_thread_specs(text: str) -> list[str]:
        """Extract and normalize thread specs."""

        values = []

        for match in THREAD_SPEC_PATTERN.finditer(text):
            size = match.group("size")
            pitch = match.group("pitch")
            values.append(f"M{size}×{pitch}")

        return list(dict.fromkeys(values))

    @staticmethod
    def _extract_quality_query_type(
        text: str,
    ) -> QualityQueryType | None:
        """Extract quality query type by keyword priority."""

        if not text:
            return None

        for query_type in QUALITY_QUERY_PRIORITY:
            keywords = QUALITY_KEYWORDS[query_type]

            if any(keyword in text for keyword in keywords):
                return query_type

        return None

    @staticmethod
    def _build_ambiguity_errors(
        *,
        sku_ids: list[str],
        oem_reference_numbers: list[str],
        thread_specs: list[str],
    ) -> list[str]:
        """Build ambiguity errors."""

        errors: list[str] = []

        if len(sku_ids) > 1:
            errors.append("multiple SKU IDs found in quality query")

        if not sku_ids and len(oem_reference_numbers) > 1:
            errors.append(
                "multiple OEM reference numbers found in quality query",
            )

        if (
            not sku_ids
            and not oem_reference_numbers
            and len(thread_specs) > 1
        ):
            errors.append("multiple thread specs found in quality query")

        return errors

    @staticmethod
    def _resolve_product_reference_type(
        *,
        sku_ids: list[str],
        oem_reference_numbers: list[str],
        thread_specs: list[str],
    ) -> ProductReferenceType | None:
        """Resolve product reference type by priority."""

        if sku_ids:
            return "sku_id"

        if oem_reference_numbers:
            return "oem_reference_number"

        if thread_specs:
            return "thread_spec"

        return None

    @staticmethod
    def _resolve_product_reference_value(
        *,
        product_reference_type: ProductReferenceType | None,
        sku_ids: list[str],
        oem_reference_numbers: list[str],
        thread_specs: list[str],
    ) -> str | None:
        """Resolve product reference value by selected type."""

        if product_reference_type == "sku_id":
            return sku_ids[0]

        if product_reference_type == "oem_reference_number":
            return oem_reference_numbers[0]

        if product_reference_type == "thread_spec":
            return thread_specs[0]

        return None