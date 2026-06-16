"""Move structured spec parser branches before not_supported fallback."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"


STRUCTURED_BRANCHES: Final[str] = '''        if self.is_max_rod_length_query(normalized_text):
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

        if thread_diameter is not None:
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

'''


def main() -> int:
    """Patch branch ordering."""

    print("=" * 80)
    print("fixing Phase 3-I-I spec parser not_supported branch order")

    errors: list[str] = []
    changes: list[str] = []

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    parse_start = content.find("    def parse(")
    if parse_start == -1:
        errors.append("parse method not found")
        pprint({"changes": changes, "errors": errors})
        return 1

    not_supported_index = content.find('            status="not_supported"', parse_start)
    if not_supported_index == -1:
        errors.append('status="not_supported" fallback not found')
        pprint({"changes": changes, "errors": errors})
        return 1

    return_index = content.rfind(
        "        return ParsedSpecQuery(",
        parse_start,
        not_supported_index,
    )
    if return_index == -1:
        errors.append("not_supported return block start not found")
        pprint({"changes": changes, "errors": errors})
        return 1

    before_not_supported = content[parse_start:return_index]

    if 'query_type="material_keyword"' in before_not_supported:
        changes.append("structured branches already appear before not_supported fallback")
    else:
        content = content[:return_index] + STRUCTURED_BRANCHES + content[return_index:]
        changes.append("inserted structured branches before not_supported fallback")

    required_markers = {
        "thread_diameter extraction": "thread_diameter = self.extract_thread_diameter",
        "material_keyword extraction": "material_keyword = self.extract_material_keyword",
        "extract_thread_diameter helper": "def extract_thread_diameter(",
        "extract_material_keyword helper": "def extract_material_keyword(",
        "max rod helper": "def is_max_rod_length_query(",
        "max ball helper": "def is_max_ball_diameter_query(",
    }

    for label, marker in required_markers.items():
        if marker not in content:
            errors.append(f"missing required parser marker: {label}")

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec parser not_supported branch order fix failed")
        return 1

    print("Phase 3-I-I spec parser not_supported branch order fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())