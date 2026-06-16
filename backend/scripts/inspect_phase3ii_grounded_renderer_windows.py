"""Inspect grounded renderer evidence and reference windows."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

TARGET_FILES: Final[tuple[Path, ...]] = (
    BACKEND_ROOT / "app/agent/rendering/grounded_renderer.py",
    BACKEND_ROOT / "app/agent/rendering/context.py",
    BACKEND_ROOT / "app/agent/rendering/schemas.py",
)


ANCHORS: Final[tuple[str, ...]] = (
    "补充说明",
    "evidence_lines",
    "reference_ids",
    "retrieved_chunks",
    "source_type",
    "chunk_id",
    "doc_id",
    "SKU",
    "spec_qa",
)


def main() -> int:
    """Inspect renderer windows."""

    print("=" * 80)
    print("inspecting Phase 3-I-I grounded renderer windows")

    errors: list[str] = []
    result: dict[str, object] = {
        "files": {},
        "errors": errors,
    }

    for file_path in TARGET_FILES:
        if not file_path.exists():
            errors.append(f"missing file: {file_path}")
            continue

        lines = file_path.read_text(encoding="utf-8").splitlines()
        rel_path = str(file_path.relative_to(BACKEND_ROOT))

        result["files"][rel_path] = {
            "anchor_lines": find_anchor_lines(lines),
            "function_windows": extract_function_windows(lines),
        }

    pprint(result)

    if errors:
        print("Phase 3-I-I grounded renderer window inspection failed")
        return 1

    print("Phase 3-I-I grounded renderer window inspection passed")
    return 0


def find_anchor_lines(
    lines: list[str],
) -> list[str]:
    """Find lines containing anchors."""

    matched: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        lowered = line.lower()

        if any(anchor.lower() in lowered for anchor in ANCHORS):
            matched.append(f"{line_number}: {line.rstrip()}")

    return matched[:260]


def extract_function_windows(
    lines: list[str],
) -> dict[str, list[str]]:
    """Extract function windows that touch evidence or references."""

    windows: dict[str, list[str]] = {}

    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if not stripped.startswith("def "):
            continue

        start = max(1, index - 6)
        end = min(len(lines), index + 110)

        window = [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ]
        joined = "\n".join(window).lower()

        if any(anchor.lower() in joined for anchor in ANCHORS):
            function_name = stripped.split("(", 1)[0].replace("def ", "")
            windows[function_name] = window

    return windows


if __name__ == "__main__":
    raise SystemExit(main())