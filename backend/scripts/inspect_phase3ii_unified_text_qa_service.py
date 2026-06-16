"""Inspect UnifiedTextQAService answer dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

TARGET_FILES: Final[tuple[Path, ...]] = (
    BACKEND_ROOT / "app/agent/services/unified_text_qa_service.py",
    BACKEND_ROOT / "app/agent/services/spec_text_qa_service.py",
    BACKEND_ROOT / "app/agent/handlers/spec_handler.py",
    BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py",
)

OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "logs/diagnostics/phase3ii_unified_text_qa_service_inspection.json"
)

ANCHORS: Final[tuple[str, ...]] = (
    "class UnifiedTextQAService",
    "def answer",
    "SpecTextQAService",
    "SpecParameterParser",
    "SpecHandler",
    "to_handler_input",
    "parsed_query",
    "handler_input",
    "handler.handle",
    "spec",
    "except",
)


def main() -> int:
    """Export focused service windows."""

    report: dict[str, Any] = {
        "files": {},
        "errors": [],
    }

    for file_path in TARGET_FILES:
        rel_path = str(file_path.relative_to(BACKEND_ROOT))

        if not file_path.exists():
            report["errors"].append(f"missing file: {file_path}")
            continue

        lines = file_path.read_text(encoding="utf-8").splitlines()

        report["files"][rel_path] = {
            "line_count": len(lines),
            "anchor_lines": find_anchor_lines(lines),
            "function_windows": extract_function_windows(lines),
        }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("UnifiedTextQAService inspection exported")
    print(f"output_file: {OUTPUT_FILE}")
    print(f"error_count: {len(report['errors'])}")
    return 1 if report["errors"] else 0


def find_anchor_lines(lines: list[str]) -> list[str]:
    """Find anchor lines."""

    matched: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        if any(anchor in line for anchor in ANCHORS):
            matched.append(f"{line_number}: {line.rstrip()}")

    return matched[:240]


def extract_function_windows(lines: list[str]) -> dict[str, list[str]]:
    """Extract windows around relevant functions/classes."""

    windows: dict[str, list[str]] = {}

    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if not stripped.startswith("def ") and not stripped.startswith("class "):
            continue

        start = max(1, index - 10)
        end = min(len(lines), index + 140)
        window = [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ]
        joined = "\n".join(window)

        if any(anchor in joined for anchor in ANCHORS):
            name = stripped.split("(", 1)[0].replace("def ", "").replace("class ", "")
            windows[name] = window

    return windows


if __name__ == "__main__":
    raise SystemExit(main())