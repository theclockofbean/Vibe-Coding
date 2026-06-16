"""Inspect core spec query files and export result to JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "logs/diagnostics"
OUTPUT_FILE: Final[Path] = OUTPUT_DIR / "phase3ii_spec_query_core_files_inspection.json"

TARGET_FILES: Final[tuple[Path, ...]] = (
    BACKEND_ROOT / "app/services/spec_query_service.py",
    BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py",
    BACKEND_ROOT / "app/agent/handlers/spec_handler.py",
    BACKEND_ROOT / "app/agent/renderers/spec_answer_renderer.py",
    BACKEND_ROOT / "app/repositories/product_repository.py",
)

FOCUS_TERMS: Final[tuple[str, ...]] = (
    "def ",
    "class ",
    "sku",
    "thread",
    "material",
    "rod",
    "ball",
    "taper",
    "螺纹",
    "材质",
    "杆长",
    "球径",
    "锥度",
    "最长",
    "最大",
    "M12",
    "M10",
    "M8",
    "ProductRepository",
)


def main() -> int:
    """Inspect core files and export JSON report."""

    errors: list[str] = []
    files_result: dict[str, Any] = {}

    for file_path in TARGET_FILES:
        rel_path = str(file_path.relative_to(BACKEND_ROOT))

        if not file_path.exists():
            errors.append(f"missing file: {file_path}")
            continue

        lines = file_path.read_text(encoding="utf-8").splitlines()

        files_result[rel_path] = {
            "line_count": len(lines),
            "signatures": extract_signatures(lines),
            "focus_lines": extract_focus_lines(lines),
            "function_windows": extract_function_windows(lines),
        }

    report: dict[str, Any] = {
        "title": "Phase 3-I-I spec query core files inspection",
        "backend_root": str(BACKEND_ROOT),
        "target_files": [
            str(path.relative_to(BACKEND_ROOT))
            for path in TARGET_FILES
        ],
        "files": files_result,
        "errors": errors,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("Phase 3-I-I spec query core inspection exported")
    print(f"output_file: {OUTPUT_FILE}")
    print(f"file_count: {len(files_result)}")
    print(f"error_count: {len(errors)}")

    if errors:
        print("errors:")
        for error in errors:
            print(f"- {error}")
        return 1

    return 0


def extract_signatures(lines: list[str]) -> list[str]:
    """Extract class/function signatures."""

    signatures: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if stripped.startswith("def ") or stripped.startswith("class "):
            signatures.append(f"{line_number}: {line.rstrip()}")

    return signatures


def extract_focus_lines(lines: list[str]) -> list[str]:
    """Extract lines with focus terms."""

    matched: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        lowered = line.lower()

        if any(term.lower() in lowered for term in FOCUS_TERMS):
            matched.append(f"{line_number}: {line.rstrip()}")

    return matched


def extract_function_windows(lines: list[str]) -> dict[str, list[str]]:
    """Extract relevant function/class windows."""

    windows: dict[str, list[str]] = {}

    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if not stripped.startswith("def ") and not stripped.startswith("class "):
            continue

        start = max(1, index - 5)
        end = min(len(lines), index + 120)
        window = [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ]
        joined = "\n".join(window).lower()

        if any(
            term.lower() in joined
            for term in (
                "sku",
                "thread",
                "material",
                "rod",
                "ball",
                "螺纹",
                "材质",
                "杆长",
                "球径",
                "最长",
                "最大",
                "ProductRepository",
            )
        ):
            name = stripped.split("(", 1)[0].replace("def ", "").replace("class ", "")
            windows[name] = window

    return windows


if __name__ == "__main__":
    raise SystemExit(main())