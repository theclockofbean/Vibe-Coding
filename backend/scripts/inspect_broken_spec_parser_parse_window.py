"""Export broken SpecParameterParser.parse window for repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

PARSER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"
OUTPUT_FILE: Final[Path] = PROJECT_ROOT / "logs/diagnostics/phase3ii_broken_spec_parser_parse_window.json"


def main() -> int:
    """Export parse method window without importing broken module."""

    lines = PARSER_FILE.read_text(encoding="utf-8").splitlines()

    parse_line = find_line(lines, "    def parse(")
    helper_line = find_next_line(
        lines,
        start_index=parse_line + 1,
        candidates=(
            "    @staticmethod",
            "    @classmethod",
            "    def ",
        ),
    )

    if helper_line is None:
        helper_line = min(len(lines), parse_line + 180)

    start = max(1, parse_line - 20)
    end = min(len(lines), helper_line + 40)

    report: dict[str, Any] = {
        "file": str(PARSER_FILE.relative_to(BACKEND_ROOT)),
        "line_count": len(lines),
        "parse_line": parse_line,
        "next_member_line": helper_line,
        "window_start": start,
        "window_end": end,
        "window": [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("broken spec parser parse window exported")
    print(f"output_file: {OUTPUT_FILE}")
    print(f"parse_line: {parse_line}")
    print(f"window: {start}-{end}")

    return 0


def find_line(lines: list[str], pattern: str) -> int:
    """Find first 1-based line number containing pattern."""

    for line_number, line in enumerate(lines, start=1):
        if pattern in line:
            return line_number

    raise RuntimeError(f"pattern not found: {pattern}")


def find_next_line(
    lines: list[str],
    *,
    start_index: int,
    candidates: tuple[str, ...],
) -> int | None:
    """Find next class member candidate."""

    for index in range(start_index, len(lines)):
        line = lines[index]

        if any(line.startswith(candidate) for candidate in candidates):
            return index + 1

    return None


if __name__ == "__main__":
    raise SystemExit(main())