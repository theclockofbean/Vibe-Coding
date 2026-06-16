"""Add runtime lazy import inside ParsedSpecQuery.to_handler_input."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"


OLD_BLOCK: Final[str] = '''    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        if self.status != "parsed" or self.query_type is None:
'''


NEW_BLOCK: Final[str] = '''    def to_handler_input(self) -> SpecHandlerInput:
        """Convert parsed query into SpecHandlerInput."""

        from app.agent.handlers.spec_handler import SpecHandlerInput

        if self.status != "parsed" or self.query_type is None:
'''


def main() -> int:
    """Patch lazy import."""

    print("=" * 80)
    print("fixing Phase 3-I-I ParsedSpecQuery.to_handler_input lazy import")

    errors: list[str] = []
    changes: list[str] = []

    if not PARSER_FILE.exists():
        errors.append(f"missing parser file: {PARSER_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = PARSER_FILE.read_text(encoding="utf-8")
    original = content

    method_start = content.find("    def to_handler_input(")
    parse_class_start = content.find("\n\nclass SpecParameterParser:", method_start)

    if method_start == -1 or parse_class_start == -1:
        errors.append("to_handler_input method window not found")
    else:
        method_window = content[method_start:parse_class_start]

        if "from app.agent.handlers.spec_handler import SpecHandlerInput" in method_window:
            changes.append("runtime lazy import already present inside to_handler_input")
        elif OLD_BLOCK in content:
            content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
            changes.append("inserted runtime lazy import inside to_handler_input")
        else:
            errors.append("to_handler_input insertion anchor not found")

    if content != original and not errors:
        PARSER_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I to_handler_input lazy import fix failed")
        return 1

    print("Phase 3-I-I to_handler_input lazy import fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())