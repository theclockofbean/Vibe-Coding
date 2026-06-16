"""Inspect spec supplemental QA rendering source."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

SEARCH_ROOTS: Final[tuple[Path, ...]] = (
    BACKEND_ROOT / "app/agent",
    BACKEND_ROOT / "app/services",
)

ANCHORS: Final[tuple[str, ...]] = (
    "补充说明",
    "参考来源",
    "spec_qa",
    "source_windows",
    "retrieved_chunks",
    "render_business_rules",
    "SPEC0005",
    "sku_exact",
    "exact_lookup",
)


def main() -> int:
    """Inspect renderer source."""

    print("=" * 80)
    print("inspecting Phase 3-I-I spec supplemental renderer")

    errors: list[str] = []
    files: list[Path] = []

    for root in SEARCH_ROOTS:
        if not root.exists():
            continue

        files.extend(sorted(root.rglob("*.py")))

    matches: dict[str, list[str]] = {}

    for file_path in files:
        rel_path = str(file_path.relative_to(BACKEND_ROOT))
        lines = file_path.read_text(encoding="utf-8").splitlines()

        matched_lines: list[str] = []

        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()

            if any(anchor.lower() in lowered for anchor in ANCHORS):
                matched_lines.append(f"{line_number}: {line.rstrip()}")

        if matched_lines:
            matches[rel_path] = matched_lines[:220]

    function_windows = extract_function_windows(files)

    result = {
        "searched_roots": [str(root.relative_to(BACKEND_ROOT)) for root in SEARCH_ROOTS],
        "matched_files": sorted(matches),
        "matches": matches,
        "function_windows": function_windows,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I spec supplemental renderer inspection failed")
        return 1

    print("Phase 3-I-I spec supplemental renderer inspection passed")
    return 0


def extract_function_windows(
    files: list[Path],
) -> dict[str, list[str]]:
    """Extract function windows that likely build supplemental text."""

    windows: dict[str, list[str]] = {}

    for file_path in files:
        rel_path = str(file_path.relative_to(BACKEND_ROOT))
        lines = file_path.read_text(encoding="utf-8").splitlines()

        for index, line in enumerate(lines, start=1):
            stripped = line.lstrip()

            if not stripped.startswith("def "):
                continue

            start = max(index - 5, 1)
            end = min(index + 90, len(lines))
            window = [
                f"{line_number}: {lines[line_number - 1]}"
                for line_number in range(start, end + 1)
            ]

            joined = "\n".join(window).lower()

            if any(anchor.lower() in joined for anchor in ANCHORS):
                function_name = stripped.split("(", 1)[0].replace("def ", "")
                windows[f"{rel_path}:{function_name}"] = window

    return windows


if __name__ == "__main__":
    raise SystemExit(main())