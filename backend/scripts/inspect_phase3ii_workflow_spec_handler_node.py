"""Inspect workflow spec handler node and handler_node_failed locations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"
OUTPUT_FILE: Final[Path] = PROJECT_ROOT / "logs/diagnostics/phase3ii_workflow_spec_handler_node.json"

ANCHORS: Final[tuple[str, ...]] = (
    "handler_node_failed",
    "SpecHandler",
    "SpecParameterParser",
    "to_handler_input",
    "parsed_query",
    "handler.handle",
    "spec_handler",
)


def main() -> int:
    """Export workflow handler-related windows."""

    lines = WORKFLOW_FILE.read_text(encoding="utf-8").splitlines()

    anchor_lines: list[str] = []
    windows: dict[str, list[str]] = {}

    for line_number, line in enumerate(lines, start=1):
        if any(anchor in line for anchor in ANCHORS):
            anchor_lines.append(f"{line_number}: {line.rstrip()}")

            start = max(1, line_number - 30)
            end = min(len(lines), line_number + 70)
            windows[f"{line_number}_{slug(line)}"] = [
                f"{current}: {lines[current - 1]}"
                for current in range(start, end + 1)
            ]

    report: dict[str, Any] = {
        "file": str(WORKFLOW_FILE.relative_to(BACKEND_ROOT)),
        "line_count": len(lines),
        "anchor_lines": anchor_lines,
        "windows": windows,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("workflow spec handler node inspection exported")
    print(f"output_file: {OUTPUT_FILE}")
    print(f"anchor_count: {len(anchor_lines)}")
    return 0


def slug(text: str) -> str:
    """Build a compact key suffix."""

    cleaned = "".join(
        char if char.isalnum() else "_"
        for char in text.strip()
    )
    return cleaned[:60] or "anchor"


if __name__ == "__main__":
    raise SystemExit(main())