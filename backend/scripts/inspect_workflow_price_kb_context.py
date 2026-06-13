"""Inspect workflow.py Price KB integration context."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


PATTERNS: Final[list[str]] = [
    "_try_real_price_kb_retrieval",
    "real_price_kb_used",
    "_state_current_query_for_price_retrieval",
    "_price_kb_retriever_enabled_from_env",
    "_price_kb_top_k_from_env",
]


def main() -> int:
    """Inspect workflow context."""

    print("=" * 80)
    print("inspecting workflow.py Price KB context")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    lines = WORKFLOW_FILE.read_text(encoding="utf-8").splitlines()

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "line_count": len(lines),
        }
    )

    for pattern in PATTERNS:
        print("\n" + "=" * 80)
        print(f"PATTERN: {pattern}")

        indexes = [
            index
            for index, line in enumerate(lines, start=1)
            if pattern in line
        ]

        if not indexes:
            print("not found")
            continue

        for line_number in indexes:
            print("-" * 80)
            print(f"line {line_number}")
            print_context(lines=lines, center=line_number, radius=8)

    return 0


def print_context(
    *,
    lines: list[str],
    center: int,
    radius: int,
) -> None:
    """Print context around line number."""

    start = max(1, center - radius)
    end = min(len(lines), center + radius)

    for line_number in range(start, end + 1):
        marker = ">>" if line_number == center else "  "
        print(f"{marker} {line_number:04d}: {lines[line_number - 1]}")


if __name__ == "__main__":
    raise SystemExit(main())