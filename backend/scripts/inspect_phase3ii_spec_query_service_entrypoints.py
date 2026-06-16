"""Inspect spec query parser and handler entrypoints."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

SEARCH_ROOTS: Final[tuple[Path, ...]] = (
    BACKEND_ROOT / "app/agent",
    BACKEND_ROOT / "app/services",
    BACKEND_ROOT / "app/repositories",
)

ANCHORS: Final[tuple[str, ...]] = (
    "spec",
    "sku",
    "thread",
    "螺纹",
    "杆长",
    "球径",
    "材质",
    "最大",
    "最长",
    "M12",
    "M8",
    "M10",
    "query",
    "parser",
    "handler",
    "structured",
    "product_repository",
    "ProductRepository",
)


def main() -> int:
    """Inspect candidate spec query entrypoints."""

    print("=" * 80)
    print("inspecting Phase 3-I-I spec query service entrypoints")

    errors: list[str] = []
    files: list[Path] = []

    for root in SEARCH_ROOTS:
        if root.exists():
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
            matches[rel_path] = matched_lines[:180]

    function_windows = extract_function_windows(files)

    result = {
        "searched_roots": [str(root.relative_to(BACKEND_ROOT)) for root in SEARCH_ROOTS],
        "matched_files": sorted(matches),
        "likely_priority_files": [
            path for path in sorted(matches)
            if any(token in path.lower() for token in ("spec", "product", "workflow", "handler", "repository"))
        ],
        "function_windows": function_windows,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I spec query entrypoint inspection failed")
        return 1

    print("Phase 3-I-I spec query entrypoint inspection passed")
    return 0


def extract_function_windows(
    files: list[Path],
) -> dict[str, list[str]]:
    """Extract relevant function windows."""

    windows: dict[str, list[str]] = {}

    focus_terms = (
        "sku",
        "thread",
        "螺纹",
        "杆长",
        "球径",
        "材质",
        "最长",
        "最大",
        "ProductRepository",
        "product_repository",
    )

    for file_path in files:
        rel_path = str(file_path.relative_to(BACKEND_ROOT))
        lines = file_path.read_text(encoding="utf-8").splitlines()

        for index, line in enumerate(lines, start=1):
            stripped = line.lstrip()

            if not stripped.startswith("def ") and not stripped.startswith("class "):
                continue

            start = max(1, index - 5)
            end = min(len(lines), index + 110)
            window = [
                f"{line_number}: {lines[line_number - 1]}"
                for line_number in range(start, end + 1)
            ]
            joined = "\n".join(window).lower()

            if any(term.lower() in joined for term in focus_terms):
                name = stripped.split("(", 1)[0].replace("def ", "").replace("class ", "")
                windows[f"{rel_path}:{name}"] = window

    return windows


if __name__ == "__main__":
    raise SystemExit(main())