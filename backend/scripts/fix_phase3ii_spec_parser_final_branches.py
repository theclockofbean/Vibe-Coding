"""Insert structured parser branches before not_spec_intent fallback."""

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
    """Patch parser fallback area."""

    print("=" * 80)
    print("fixing Phase 3-I-I spec parser final structured branches")

    errors: list[str] = []
    changes: list[str] = []

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    if 'query_type="material_keyword"' in content:
        changes.append("structured parser branches already present")
        pprint({"changes": changes, "errors": errors})
        return 0

    parse_start = content.find("    def parse(")
    if parse_start == -1:
        errors.append("parse method not found")
        pprint({"changes": changes, "errors": errors})
        return 1

    fallback_index = content.find('            status="not_spec_intent"', parse_start)
    if fallback_index == -1:
        errors.append('status="not_spec_intent" fallback not found after parse method')
        pprint({"changes": changes, "errors": errors})
        return 1

    return_index = content.rfind("        return ParsedSpecQuery(", parse_start, fallback_index)
    if return_index == -1:
        errors.append("fallback return ParsedSpecQuery block not found")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = content[:return_index] + STRUCTURED_BRANCHES + content[return_index:]
    changes.append("inserted structured branches before not_spec_intent fallback")

    if "thread_diameter = self.extract_thread_diameter" not in content:
        errors.append("thread_diameter extraction is missing; rerun previous patch first")

    if "material_keyword = self.extract_material_keyword" not in content:
        errors.append("material_keyword extraction is missing; rerun previous patch first")

    if "def extract_thread_diameter(" not in content:
        errors.append("extract_thread_diameter helper is missing; rerun previous patch first")

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec parser final branch fix failed")
        return 1

    print("Phase 3-I-I spec parser final branch fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())