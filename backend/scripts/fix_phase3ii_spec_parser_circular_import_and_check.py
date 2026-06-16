"""Fix spec parser circular import and parser check mypy issue."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"
CHECK_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_spec_parser_structured_queries.py"


LOCAL_SPEC_QUERY_TYPE_BLOCK: Final[str] = '''if TYPE_CHECKING:
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
]
'''


def main() -> int:
    """Apply fixes."""

    print("=" * 80)
    print("fixing Phase 3-I-I spec parser circular import and check script")

    errors: list[str] = []
    changes: list[str] = []

    patch_parser(errors=errors, changes=changes)
    patch_check_script(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I parser circular import fix failed")
        return 1

    print("Phase 3-I-I parser circular import fix completed")
    return 0


def patch_parser(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch spec_parameter_parser.py."""

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        return

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    if "from typing import TYPE_CHECKING, Literal" not in content:
        anchor = "from __future__ import annotations\n\n"
        if anchor not in content:
            errors.append("future import anchor not found")
        else:
            content = content.replace(
                anchor,
                anchor + "from typing import TYPE_CHECKING, Literal\n",
                1,
            )
            changes.append("added TYPE_CHECKING and Literal import")

    old_import = "from app.agent.handlers.spec_handler import SpecHandlerInput, SpecQueryType\n"
    if old_import in content:
        content = content.replace(old_import, LOCAL_SPEC_QUERY_TYPE_BLOCK + "\n", 1)
        changes.append("replaced runtime handler import with local SpecQueryType")
    elif "SpecQueryType = Literal[" in content and "if TYPE_CHECKING:" in content:
        changes.append("parser circular import already replaced")
    else:
        errors.append("runtime handler import anchor not found")

    old_to_handler = '''    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        if self.status != "parsed" or self.query_type is None:
'''

    new_to_handler = '''    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        from app.agent.handlers.spec_handler import SpecHandlerInput

        if self.status != "parsed" or self.query_type is None:
'''

    if "from app.agent.handlers.spec_handler import SpecHandlerInput" not in content:
        if old_to_handler not in content:
            errors.append("to_handler_input lazy import anchor not found")
        else:
            content = content.replace(old_to_handler, new_to_handler, 1)
            changes.append("added lazy SpecHandlerInput import inside to_handler_input")
    else:
        changes.append("lazy SpecHandlerInput import already present")

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")


def patch_check_script(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch targeted check script type annotation."""

    if not CHECK_FILE.exists():
        errors.append(f"missing check file: {CHECK_FILE}")
        return

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content

    if "from typing import Any, Final, NamedTuple" not in content:
        content = content.replace(
            "from typing import Final, NamedTuple",
            "from typing import Any, Final, NamedTuple",
            1,
        )
        changes.append("added Any import to targeted check")

    if "rows: list[dict[str, object]] = []" in content:
        content = content.replace(
            "rows: list[dict[str, object]] = []",
            "rows: list[dict[str, Any]] = []",
            1,
        )
        changes.append("widened rows type to dict[str, Any]")
    elif "rows: list[dict[str, Any]] = []" in content:
        changes.append("rows type already widened")
    else:
        errors.append("rows annotation anchor not found")

    if content != original and not errors:
        CHECK_FILE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())