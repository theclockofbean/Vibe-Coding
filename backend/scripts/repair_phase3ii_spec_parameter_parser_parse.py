"""Repair SpecParameterParser.parse after broken structured branch insertion."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"


PARSE_METHOD: Final[str] = '''    def parse(self, text: str, *, limit: int = 20) -> ParsedSpecQuery:
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

        return ParsedSpecQuery(
            status="not_supported",
            raw_text=raw_text,
            errors=[
                "no SKU ID, OEM reference number, thread spec, material, or range query was found"
            ],
        )

'''


HELPERS: Final[str] = '''    @classmethod
    def extract_thread_diameter(
        cls,
        text: str,
    ) -> str | None:
        """Extract metric thread diameter without requiring pitch."""

        for match in re.finditer(
            r"(?<![A-Za-z0-9])M(?P<diameter>\\d+(?:\\.\\d+)?)(?!\\s*[×xX*＊]\\s*\\d)(?![A-Za-z0-9])",
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

'''


def main() -> int:
    """Repair parser."""

    print("=" * 80)
    print("repairing Phase 3-I-I SpecParameterParser.parse")

    errors: list[str] = []
    changes: list[str] = []

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    content = repair_to_handler_input(content, changes, errors)
    content = replace_parse_method(content, changes, errors)
    content = insert_helpers(content, changes, errors)

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I SpecParameterParser repair failed")
        return 1

    print("Phase 3-I-I SpecParameterParser repair completed")
    return 0


def repair_to_handler_input(
    content: str,
    changes: list[str],
    errors: list[str],
) -> str:
    """Add lazy SpecHandlerInput import to avoid circular imports."""

    old_block = '''    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        if self.status != "parsed" or self.query_type is None:
'''

    new_block = '''    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        from app.agent.handlers.spec_handler import SpecHandlerInput

        if self.status != "parsed" or self.query_type is None:
'''

    if "from app.agent.handlers.spec_handler import SpecHandlerInput" in content:
        changes.append("lazy SpecHandlerInput import already present")
        return content

    if old_block not in content:
        errors.append("to_handler_input anchor not found")
        return content

    changes.append("added lazy SpecHandlerInput import")
    return content.replace(old_block, new_block, 1)


def replace_parse_method(
    content: str,
    changes: list[str],
    errors: list[str],
) -> str:
    """Replace the whole parse method."""

    parse_start = content.find("    def parse(")
    if parse_start == -1:
        errors.append("parse method start not found")
        return content

    next_member_start = content.find("    @staticmethod\n    def extract_sku_ids", parse_start)
    if next_member_start == -1:
        errors.append("extract_sku_ids anchor not found")
        return content

    changes.append("replaced broken parse method")
    return content[:parse_start] + PARSE_METHOD + content[next_member_start:]


def insert_helpers(
    content: str,
    changes: list[str],
    errors: list[str],
) -> str:
    """Insert helper methods before _build_priority_warnings."""

    if "def extract_thread_diameter(" in content:
        changes.append("structured helper methods already present")
        return content

    anchor = "    @staticmethod\n    def _build_priority_warnings("
    if anchor not in content:
        errors.append("_build_priority_warnings anchor not found")
        return content

    changes.append("inserted structured helper methods")
    return content.replace(anchor, HELPERS + anchor, 1)


if __name__ == "__main__":
    raise SystemExit(main())