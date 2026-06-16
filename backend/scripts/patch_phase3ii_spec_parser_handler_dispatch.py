"""Patch spec parser and handler dispatch for structured query capabilities."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"
HANDLER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/handlers/spec_handler.py"


NEW_SPEC_QUERY_TYPE_BLOCK: Final[str] = '''SpecQueryType = Literal[
    "sku_id",
    "sku_ids",
    "thread_spec",
    "thread_dimensions",
    "thread_diameter",
    "material_keyword",
    "max_rod_length",
    "max_ball_diameter",
    "oem_reference_number",
]
'''


HANDLER_BRANCHES: Final[str] = '''        if handler_input.query_type == "thread_diameter":
            diameter_mm = self._parse_decimal(
                handler_input.diameter_mm,
                field_name="diameter_mm",
            )

            return self._spec_query_service.query_by_thread_diameter(
                diameter_mm=diameter_mm,
                limit=handler_input.limit,
            )

        if handler_input.query_type == "material_keyword":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_material_keyword(
                query_value,
                limit=handler_input.limit,
            )

        if handler_input.query_type == "max_rod_length":
            return self._spec_query_service.query_by_max_rod_length(
                limit=handler_input.limit,
            )

        if handler_input.query_type == "max_ball_diameter":
            return self._spec_query_service.query_by_max_ball_diameter(
                limit=handler_input.limit,
            )

'''


PARSER_HELPERS: Final[str] = '''
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
    """Patch parser and handler."""

    print("=" * 80)
    print("patching Phase 3-I-I spec parser and handler dispatch")

    errors: list[str] = []
    changes: list[str] = []

    patch_handler(errors=errors, changes=changes)
    patch_parser(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec parser/handler dispatch patch failed")
        return 1

    print("Phase 3-I-I spec parser/handler dispatch patch completed")
    return 0


def patch_handler(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch SpecHandler query types and dispatch."""

    if not HANDLER_FILE.exists():
        errors.append(f"missing handler file: {HANDLER_FILE}")
        return

    content = HANDLER_FILE.read_text(encoding="utf-8")
    original = content

    start = content.find("SpecQueryType = Literal[")
    end_marker = "\n\nSpecHandlerStatus"
    end = content.find(end_marker, start)

    if start == -1 or end == -1:
        errors.append("SpecQueryType block not found")
    else:
        old_block = content[start:end]
        if '"thread_diameter"' not in old_block:
            content = content[:start] + NEW_SPEC_QUERY_TYPE_BLOCK + content[end:]
            changes.append("extended SpecQueryType literal")
        else:
            changes.append("SpecQueryType literal already extended")

    if 'handler_input.query_type == "thread_diameter"' not in content:
        anchor = '        if handler_input.query_type == "oem_reference_number":\n'
        if anchor not in content:
            errors.append("handler oem branch anchor not found")
        else:
            content = content.replace(anchor, HANDLER_BRANCHES + anchor, 1)
            changes.append("inserted handler dispatch branches")
    else:
        changes.append("handler dispatch branches already present")

    if content != original and not errors:
        HANDLER_FILE.write_text(content, encoding="utf-8")


def patch_parser(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch SpecParameterParser recognition."""

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        return

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    old_extract = '''        thread_specs = self.extract_thread_specs(normalized_text)

        warnings = self._build_priority_warnings(
'''

    new_extract = '''        thread_specs = self.extract_thread_specs(normalized_text)
        thread_diameter = self.extract_thread_diameter(normalized_text)
        material_keyword = self.extract_material_keyword(normalized_text)

        warnings = self._build_priority_warnings(
'''

    if "thread_diameter = self.extract_thread_diameter" not in content:
        if old_extract not in content:
            errors.append("parser extraction anchor not found")
        else:
            content = content.replace(old_extract, new_extract, 1)
            changes.append("added thread_diameter and material extraction")
    else:
        changes.append("parser extraction already patched")

    old_final_return = '''        return ParsedSpecQuery(
            raw_text=text,
            normalized_text=normalized_text,
            status="not_spec_intent",
            errors=[
                "no SKU ID, OEM reference number, or thread spec was found"
            ],
        )
'''

    new_branches = '''        if thread_diameter is not None:
            return ParsedSpecQuery(
                raw_text=text,
                normalized_text=normalized_text,
                status="parsed",
                query_type="thread_diameter",
                diameter_mm=thread_diameter,
                limit=limit,
                warnings=warnings,
            )

        if material_keyword is not None:
            return ParsedSpecQuery(
                raw_text=text,
                normalized_text=normalized_text,
                status="parsed",
                query_type="material_keyword",
                query_value=material_keyword,
                limit=limit,
                warnings=warnings,
            )

        if self.is_max_rod_length_query(normalized_text):
            return ParsedSpecQuery(
                raw_text=text,
                normalized_text=normalized_text,
                status="parsed",
                query_type="max_rod_length",
                limit=limit,
                warnings=warnings,
            )

        if self.is_max_ball_diameter_query(normalized_text):
            return ParsedSpecQuery(
                raw_text=text,
                normalized_text=normalized_text,
                status="parsed",
                query_type="max_ball_diameter",
                limit=limit,
                warnings=warnings,
            )

        return ParsedSpecQuery(
            raw_text=text,
            normalized_text=normalized_text,
            status="not_spec_intent",
            errors=[
                "no SKU ID, OEM reference number, thread spec, material, or range query was found"
            ],
        )
'''

    if 'query_type="material_keyword"' not in content:
        if old_final_return not in content:
            errors.append("parser final return anchor not found")
        else:
            content = content.replace(old_final_return, new_branches, 1)
            changes.append("inserted parser structured query branches")
    else:
        changes.append("parser structured query branches already present")

    if "def extract_thread_diameter(" not in content:
        anchor = "    @staticmethod\n    def _build_priority_warnings(\n"
        if anchor not in content:
            errors.append("parser helper insertion anchor not found")
        else:
            content = content.replace(anchor, PARSER_HELPERS + anchor, 1)
            changes.append("inserted parser helper methods")
    else:
        changes.append("parser helper methods already present")

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())