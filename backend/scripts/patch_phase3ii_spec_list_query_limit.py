"""Raise list-style spec query limits for thread diameter and material queries."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
HANDLER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/handlers/spec_handler.py"


OLD_THREAD_BRANCH: Final[str] = '''        if handler_input.query_type == "thread_diameter":
            diameter_mm = self._parse_decimal(
                handler_input.diameter_mm,
                field_name="diameter_mm",
            )

            return self._spec_query_service.query_by_thread_diameter(
                diameter_mm=diameter_mm,
                limit=handler_input.limit,
            )
'''


NEW_THREAD_BRANCH: Final[str] = '''        if handler_input.query_type == "thread_diameter":
            diameter_mm = self._parse_decimal(
                handler_input.diameter_mm,
                field_name="diameter_mm",
            )

            return self._spec_query_service.query_by_thread_diameter(
                diameter_mm=diameter_mm,
                limit=max(handler_input.limit, 50),
            )
'''


OLD_MATERIAL_BRANCH: Final[str] = '''        if handler_input.query_type == "material_keyword":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_material_keyword(
                query_value,
                limit=handler_input.limit,
            )
'''


NEW_MATERIAL_BRANCH: Final[str] = '''        if handler_input.query_type == "material_keyword":
            query_value = self._require_query_value(handler_input)
            return self._spec_query_service.query_by_material_keyword(
                query_value,
                limit=max(handler_input.limit, 50),
            )
'''


def main() -> int:
    """Patch list query limits."""

    print("=" * 80)
    print("patching Phase 3-I-I spec list query limit")

    errors: list[str] = []
    changes: list[str] = []

    if not HANDLER_FILE.exists():
        errors.append(f"missing handler file: {HANDLER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = HANDLER_FILE.read_text(encoding="utf-8")
    original = content

    if OLD_THREAD_BRANCH in content:
        content = content.replace(OLD_THREAD_BRANCH, NEW_THREAD_BRANCH, 1)
        changes.append("raised thread_diameter query limit to at least 50")
    elif "query_by_thread_diameter" in content and "limit=max(handler_input.limit, 50)" in content:
        changes.append("thread_diameter limit already raised")
    else:
        errors.append("thread_diameter handler branch anchor not found")

    if OLD_MATERIAL_BRANCH in content:
        content = content.replace(OLD_MATERIAL_BRANCH, NEW_MATERIAL_BRANCH, 1)
        changes.append("raised material_keyword query limit to at least 50")
    elif "query_by_material_keyword" in content and "limit=max(handler_input.limit, 50)" in content:
        changes.append("material_keyword limit already raised")
    else:
        errors.append("material_keyword handler branch anchor not found")

    if content != original and not errors:
        HANDLER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec list query limit patch failed")
        return 1

    print("Phase 3-I-I spec list query limit patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())