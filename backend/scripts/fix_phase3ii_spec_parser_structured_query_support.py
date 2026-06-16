"""Add structured spec query support to SpecParameterParser."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"


EXTRACTION_OLD: Final[str] = '''        sku_ids = self.extract_sku_ids(normalized_text)
        oem_numbers = self.extract_oem_reference_numbers(normalized_text)
        thread_specs = self.extract_thread_specs(normalized_text)

        warnings = self._build_priority_warnings(
'''


EXTRACTION_NEW: Final[str] = '''        sku_ids = self.extract_sku_ids(normalized_text)
        oem_numbers = self.extract_oem_reference_numbers(normalized_text)
        thread_specs = self.extract_thread_specs(normalized_text)
        thread_diameter = self.extract_thread_diameter(normalized_text)
        material_keyword = self.extract_material_keyword(normalized_text)

        warnings = self._build_priority_warnings(
'''


STRUCTURED_BRANCHES: Final[str] = '''        if self.is_max_rod_length_query(normalized_text):
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

'''


HELPERS: Final[str] = '''
    @classmethod
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
    """Patch SpecParameterParser."""

    print("=" * 80)
    print("fixing Phase 3-I-I spec parser structured query support")

    errors: list[str] = []
    changes: list[str] = []

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    if "thread_diameter = self.extract_thread_diameter" not in content:
        if EXTRACTION_OLD not in content:
            errors.append("extraction anchor not found")
        else:
            content = content.replace(EXTRACTION_OLD, EXTRACTION_NEW, 1)
            changes.append("added thread_diameter/material extraction")
    else:
        changes.append("extraction already present")

    if 'query_type="material_keyword"' not in content:
        parse_start = content.find("    def parse(")
        fallback_index = content.find('            status="not_supported"', parse_start)

        if parse_start == -1:
            errors.append("parse method not found")
        elif fallback_index == -1:
            errors.append("not_supported fallback not found")
        else:
            return_index = content.rfind(
                "        return ParsedSpecQuery(",
                parse_start,
                fallback_index,
            )

            if return_index == -1:
                errors.append("not_supported return block not found")
            else:
                content = content[:return_index] + STRUCTURED_BRANCHES + content[return_index:]
                changes.append("inserted structured branches before not_supported fallback")
    else:
        changes.append("structured branches already present")

    if "def extract_thread_diameter(" not in content:
        helper_anchor = "    @staticmethod\n    def _build_priority_warnings("
        if helper_anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(helper_anchor, HELPERS + helper_anchor, 1)
            changes.append("inserted structured parser helpers")
    else:
        changes.append("structured parser helpers already present")

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec parser structured query support fix failed")
        return 1

    print("Phase 3-I-I spec parser structured query support fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())