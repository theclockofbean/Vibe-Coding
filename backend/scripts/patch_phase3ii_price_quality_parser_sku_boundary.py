"""Patch price and quality parser SKU regex for Chinese-adjacent SKU text."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

PRICE_PARSER_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/parsers/price_parameter_parser.py"
)
QUALITY_PARSER_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/parsers/quality_parameter_parser.py"
)


def main() -> int:
    """Patch price and quality SKU regex patterns."""

    print("=" * 80)
    print("patching price and quality parser SKU boundary regex")

    errors: list[str] = []
    changes: list[dict[str, object]] = []

    patch_file(
        file_path=PRICE_PARSER_FILE,
        old=r'r"\bSKU[-_\s]?(?P<number>\d{1,3})\b"',
        new=r'r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])"',
        label="price",
        changes=changes,
        errors=errors,
    )

    patch_file(
        file_path=QUALITY_PARSER_FILE,
        old=r'r"\bSKU\d{3,}\b"',
        new=r'r"(?<![A-Za-z0-9])SKU\d{3,}(?![A-Za-z0-9])"',
        label="quality",
        changes=changes,
        errors=errors,
    )

    pprint(
        {
            "changes": changes,
            "errors": errors,
        }
    )

    if errors:
        print("price/quality parser SKU boundary patch failed")
        return 1

    print("price/quality parser SKU boundary patch completed")
    return 0


def patch_file(
    *,
    file_path: Path,
    old: str,
    new: str,
    label: str,
    changes: list[dict[str, object]],
    errors: list[str],
) -> None:
    """Patch one source file."""

    if not file_path.exists():
        errors.append(f"missing {label} parser file: {file_path}")
        return

    content = file_path.read_text(encoding="utf-8")
    original = content

    if old in content:
        content = content.replace(old, new, 1)
        changed = True
    elif new in content:
        changed = False
    else:
        errors.append(f"{label}: target SKU regex anchor not found")
        return

    if content != original:
        file_path.write_text(content, encoding="utf-8")

    changes.append(
        {
            "label": label,
            "file": str(file_path),
            "changed": changed,
            "old": old,
            "new": new,
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())