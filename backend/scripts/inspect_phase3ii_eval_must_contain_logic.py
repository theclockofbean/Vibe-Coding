"""Inspect Phase 3-I-I evaluator must-contain matching logic."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"

ANCHORS: Final[tuple[str, ...]] = (
    "must_contain_all",
    "must_contain_any",
    "missing must_contain_all",
    "missing any of must_contain_any",
    "final_response",
    "fragment",
    "normalize",
)


def main() -> int:
    """Inspect evaluator must-contain logic."""

    print("=" * 80)
    print("inspecting Phase 3-I-I evaluator must-contain logic")

    errors: list[str] = []

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        pprint({"errors": errors})
        return 1

    content = EVAL_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()

    result = {
        "file": str(EVAL_FILE.relative_to(BACKEND_ROOT)),
        "line_count": len(lines),
        "matched_lines": extract_matched_lines(lines),
        "function_windows": extract_relevant_function_windows(lines),
        "string_presence": {
            "normalize_for_format_compare": "normalize_for_format_compare" in content,
            "normalize_text": "normalize_text" in content,
            ".00mm": ".00mm" in content,
            ".00 mm": ".00 mm" in content,
            "missing must_contain_all": "missing must_contain_all" in content,
            "must_contain_any": "must_contain_any" in content,
        },
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I evaluator must-contain logic inspection failed")
        return 1

    print("Phase 3-I-I evaluator must-contain logic inspection passed")
    return 0


def extract_matched_lines(lines: list[str]) -> list[str]:
    """Extract matched lines."""

    matched: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        lowered = line.lower()

        if any(anchor.lower() in lowered for anchor in ANCHORS):
            matched.append(f"{line_number}: {line.rstrip()}")

    return matched[:220]


def extract_relevant_function_windows(lines: list[str]) -> dict[str, list[str]]:
    """Extract function windows containing must-contain logic."""

    windows: dict[str, list[str]] = {}

    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if not stripped.startswith("def "):
            continue

        function_name = stripped.split("(", 1)[0].replace("def ", "")
        start = max(index - 6, 1)
        end = min(index + 100, len(lines))
        window = [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ]

        joined = "\n".join(window).lower()

        if any(anchor.lower() in joined for anchor in ANCHORS):
            windows[function_name] = window

    return windows


if __name__ == "__main__":
    raise SystemExit(main())