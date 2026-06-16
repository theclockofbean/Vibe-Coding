"""Rule-based parser for simple specification query parameters.

This parser extracts deterministic identifiers from simple customer text:
SKU IDs, OEM reference numbers, and metric thread specs.

It does not call an LLM and does not query the database.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final, Literal, TypeAlias

if TYPE_CHECKING:
    from app.agent.handlers.spec_handler import SpecHandlerInput


SpecQueryType = Literal[
    "sku_id",
    "sku_ids",
    "thread_spec",
    "thread_dimensions",
    "thread_diameter",
    "material_keyword",
    "max_rod_length",
    "max_ball_diameter",
    "oem_reference_number",
    "product_name_keyword",
]


ParseStatus: TypeAlias = Literal[
    "parsed",
    "not_supported",
    "ambiguous",
]

SKU_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])",
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


@dataclass(frozen=True)
class ParsedSpecQuery:
    """Parsed specification query parameters."""

    status: ParseStatus
    raw_text: str
    query_type: SpecQueryType | None = None
    query_value: str | None = None
    sku_ids: list[str] = field(default_factory=list)
    diameter_mm: str | None = None
    pitch_mm: str | None = None
    limit: int = 20
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""

        return asdict(self)

    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        from app.agent.handlers.spec_handler import SpecHandlerInput

        if self.status != "parsed" or self.query_type is None:
            raise ValueError("only parsed query can be converted to handler input")

        return SpecHandlerInput(
            query_type=self.query_type,
            query_value=self.query_value,
            sku_ids=self.sku_ids,
            diameter_mm=self.diameter_mm,
            pitch_mm=self.pitch_mm,
            limit=self.limit,
        )


class SpecParameterParser:
    """Extract simple specification query parameters from customer text."""

    def parse(self, text: str, *, limit: int = 20) -> ParsedSpecQuery:
        """Parse customer text into structured specification query parameters."""

        raw_text = text
        normalized_text = text.strip()

        if not normalized_text:
            return ParsedSpecQuery(
                status="not_supported",
                raw_text=raw_text,
                errors=["text must not be blank"],
            )

        if limit <= 0:
            return ParsedSpecQuery(
                status="not_supported",
                raw_text=raw_text,
                errors=["limit must be positive"],
            )

        sku_ids = self.extract_sku_ids(normalized_text)
        oem_numbers = self.extract_oem_reference_numbers(normalized_text)
        thread_specs = self.extract_thread_specs(normalized_text)
        thread_diameter = self.extract_thread_diameter(normalized_text)
        material_keyword = self.extract_material_keyword(normalized_text)
        product_name_keyword = self.extract_product_name_keyword(normalized_text)

        warnings = self._build_priority_warnings(
            sku_ids=sku_ids,
            oem_numbers=oem_numbers,
            thread_specs=thread_specs,
        )

        if sku_ids:
            if len(sku_ids) == 1:
                return ParsedSpecQuery(
                    status="parsed",
                    raw_text=raw_text,
                    query_type="sku_id",
                    query_value=sku_ids[0],
                    limit=limit,
                    warnings=warnings,
                )

            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="sku_ids",
                sku_ids=sku_ids,
                limit=limit,
                warnings=warnings,
            )

        if oem_numbers:
            if len(oem_numbers) == 1:
                return ParsedSpecQuery(
                    status="parsed",
                    raw_text=raw_text,
                    query_type="oem_reference_number",
                    query_value=oem_numbers[0],
                    limit=limit,
                    warnings=warnings,
                )

            return ParsedSpecQuery(
                status="ambiguous",
                raw_text=raw_text,
                errors=["multiple OEM reference numbers found"],
            )

        if thread_specs:
            if len(thread_specs) == 1:
                return ParsedSpecQuery(
                    status="parsed",
                    raw_text=raw_text,
                    query_type="thread_spec",
                    query_value=thread_specs[0],
                    limit=limit,
                    warnings=warnings,
                )

            return ParsedSpecQuery(
                status="ambiguous",
                raw_text=raw_text,
                errors=["multiple thread specs found"],
            )

        if self.is_max_rod_length_query(normalized_text):
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="max_rod_length",
                limit=limit,
                warnings=warnings,
            )

        if self.is_max_ball_diameter_query(normalized_text):
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="max_ball_diameter",
                limit=limit,
                warnings=warnings,
            )

        if thread_diameter is not None:
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="thread_diameter",
                diameter_mm=thread_diameter,
                limit=limit,
                warnings=warnings,
            )

        if material_keyword is not None:
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="material_keyword",
                query_value=material_keyword,
                limit=limit,
                warnings=warnings,
            )

        if product_name_keyword is not None:
            return ParsedSpecQuery(
                status="parsed",
                raw_text=raw_text,
                query_type="product_name_keyword",
                query_value=product_name_keyword,
                limit=limit,
                warnings=warnings,
            )

        return ParsedSpecQuery(
            status="not_supported",
            raw_text=raw_text,
            errors=[
                "no SKU ID, OEM reference number, thread spec, material, or range query was found"
            ],
        )

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


    @classmethod
    def extract_thread_diameter(
        cls,
        text: str,
    ) -> str | None:
        """Extract metric thread diameter without requiring pitch."""

        for match in re.finditer(
            r"(?<![A-Za-z0-9])M(?P<diameter>\d+(?:\.\d+)?)(?!\s*[×xX*＊]\s*\d)(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        ):
            diameter = cls._normalize_decimal_text(match.group("diameter"))

            if diameter is not None:
                return diameter

        return None

    @staticmethod
    def extract_material_keyword(
        text: str,
    ) -> str | None:
        """Extract supported material keyword."""

        for keyword in ("钛合金", "碳纤维", "不锈钢", "铝合金", "黄铜", "真皮"):
            if keyword in text:
                return keyword

        return None

    @staticmethod
    def extract_product_name_keyword(
        text: str,
    ) -> str | None:
        """Extract supported product name or series keyword."""

        for keyword in ("夜光",):
            if keyword in text and (
                "系列" in text
                or "螺纹" in text
                or "规格" in text
                or "球头" in text
            ):
                return keyword

        return None

    @staticmethod
    def is_max_rod_length_query(
        text: str,
    ) -> bool:
        """Return whether query asks for longest rod length."""

        return (
            ("最长" in text and "杆" in text)
            or "杆长最大" in text
            or "最大杆长" in text
        )

    @staticmethod
    def is_max_ball_diameter_query(
        text: str,
    ) -> bool:
        """Return whether query asks for maximum ball diameter."""

        return (
            ("最大" in text and "球径" in text)
            or "球径最大" in text
            or ("最大" in text and "球头" in text)
        )

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