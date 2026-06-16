"""Inspect source windows for Answer Strategy risk gate patching."""

from __future__ import annotations

import json
import re
from pathlib import Path
from pprint import pprint
from typing import Any, Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

ANSWER_STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)

CONFIG_CANDIDATES: Final[tuple[Path, ...]] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json",
    BACKEND_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json",
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.md",
)


SOURCE_ANCHORS: Final[tuple[str, ...]] = (
    "def decide_answer_strategy",
    "def load_answer_strategy_config",
    "def detect_forbidden_fragments",
    "def build_decision",
    "def build_boundary_notes",
    "SAFETY_MODE",
    "SPLIT_MODE",
    "BOUNDARY_NOTES",
)


def main() -> int:
    """Print answer strategy source windows and config summary."""

    print("=" * 80)
    print("inspecting Phase 3-I-I answer strategy source windows")

    errors: list[str] = []

    source_result = inspect_source_windows(errors=errors)
    config_result = inspect_config_candidates()

    result = {
        "source_result": source_result,
        "config_result": config_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I answer strategy source window inspection failed")
        return 1

    print("Phase 3-I-I answer strategy source window inspection passed")
    return 0


def inspect_source_windows(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect source windows around anchors."""

    if not ANSWER_STRATEGY_FILE.exists():
        errors.append(f"missing file: {ANSWER_STRATEGY_FILE}")
        return {"exists": False, "path": str(ANSWER_STRATEGY_FILE)}

    content = ANSWER_STRATEGY_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()

    windows: dict[str, list[str]] = {}

    for anchor in SOURCE_ANCHORS:
        anchor_line = find_line_number(lines=lines, anchor=anchor)

        if anchor_line is None:
            windows[anchor] = ["NOT_FOUND"]
            continue

        windows[anchor] = source_window(
            lines=lines,
            center_line=anchor_line,
            before=12,
            after=55,
        )

    return {
        "exists": True,
        "path": str(ANSWER_STRATEGY_FILE.relative_to(BACKEND_ROOT)),
        "line_count": len(lines),
        "windows": windows,
        "string_presence": {
            "primary_with_boundary_note": "primary_with_boundary_note" in content,
            "single_primary": "single_primary" in content,
            "safety_blocked": "safety_blocked" in content,
            "split_required": "split_required" in content,
            "high_risk_fragments": "high_risk_fragments" in content,
            "handoff_required": "handoff_required" in content,
        },
    }


def inspect_config_candidates() -> list[dict[str, Any]]:
    """Inspect possible config files."""

    results: list[dict[str, Any]] = []

    for path in CONFIG_CANDIDATES:
        if not path.exists():
            results.append(
                {
                    "exists": False,
                    "path": str(path),
                }
            )
            continue

        content = path.read_text(encoding="utf-8")
        item: dict[str, Any] = {
            "exists": True,
            "path": str(path),
            "suffix": path.suffix,
            "string_presence": {
                "primary_with_boundary_note": "primary_with_boundary_note" in content,
                "single_primary": "single_primary" in content,
                "safety_blocked": "safety_blocked" in content,
                "split_required": "split_required" in content,
                "high_risk_fragments": "high_risk_fragments" in content,
                "handoff_required": "handoff_required" in content,
            },
            "risk_related_lines": extract_lines(
                content=content,
                markers=(
                    "primary_with_boundary_note",
                    "single_primary",
                    "safety_blocked",
                    "split_required",
                    "high_risk_fragments",
                    "handoff_required",
                    "boundary_note_type",
                    "mode",
                    "rules",
                ),
                limit=160,
            ),
        }

        if path.suffix == ".json":
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                item["json_error"] = str(exc)
            else:
                item["json_summary"] = summarize_json_config(parsed)

        results.append(item)

    return results


def summarize_json_config(
    parsed: Any,
) -> dict[str, Any]:
    """Summarize JSON config without assuming exact schema."""

    if not isinstance(parsed, dict):
        return {"type": type(parsed).__name__}

    summary: dict[str, Any] = {
        "top_level_keys": sorted(str(key) for key in parsed.keys()),
    }

    for key, value in parsed.items():
        if isinstance(value, dict):
            summary[f"{key}_keys"] = sorted(str(item_key) for item_key in value.keys())
        elif isinstance(value, list):
            summary[f"{key}_len"] = len(value)
            summary[f"{key}_first_items"] = value[:3]

    return summary


def find_line_number(
    *,
    lines: list[str],
    anchor: str,
) -> int | None:
    """Find 1-based line number for anchor."""

    for index, line in enumerate(lines, start=1):
        if anchor in line:
            return index

    return None


def source_window(
    *,
    lines: list[str],
    center_line: int,
    before: int,
    after: int,
) -> list[str]:
    """Return source window around a 1-based line number."""

    start = max(center_line - before, 1)
    end = min(center_line + after, len(lines))

    return [
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start, end + 1)
    ]


def extract_lines(
    *,
    content: str,
    markers: tuple[str, ...],
    limit: int,
) -> list[str]:
    """Extract lines containing markers."""

    results: list[str] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        lowered = line.lower()

        if any(marker.lower() in lowered for marker in markers):
            results.append(f"{line_number}: {line.rstrip()}")

    return results[:limit]


if __name__ == "__main__":
    raise SystemExit(main())