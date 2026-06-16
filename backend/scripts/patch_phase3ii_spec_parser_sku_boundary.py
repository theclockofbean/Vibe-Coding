"""Patch SpecParameterParser SKU regex for Chinese-adjacent SKU text."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SPEC_PARSER_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"
)


def main() -> int:
    """Patch spec parser SKU regex."""

    print("=" * 80)
    print("patching SpecParameterParser SKU boundary regex")

    if not SPEC_PARSER_FILE.exists():
        pprint({"error": f"missing parser file: {SPEC_PARSER_FILE}"})
        return 1

    content = SPEC_PARSER_FILE.read_text(encoding="utf-8")
    original = content

    old = r'r"\bSKU[-_\s]?(?P<number>\d{1,3})\b"'
    new = r'r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])"'

    if old in content:
        content = content.replace(old, new, 1)
        changed = True
    elif new in content:
        changed = False
    else:
        pprint(
            {
                "error": "target SKU regex anchor not found",
                "file": str(SPEC_PARSER_FILE),
            }
        )
        return 1

    if content != original:
        SPEC_PARSER_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "file": str(SPEC_PARSER_FILE),
            "changed": changed,
            "old": old,
            "new": new,
        }
    )

    print("SpecParameterParser SKU boundary regex patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())