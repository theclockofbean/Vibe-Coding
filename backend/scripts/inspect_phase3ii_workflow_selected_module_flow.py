"""Inspect Workflow selected_module flow for Phase 3-I-I P0 routing."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"
STATE_FILE: Final[Path] = BACKEND_ROOT / "app/agent/state.py"

ANCHORS: Final[tuple[str, ...]] = (
    "llm_intent",
    "selected_module",
    "candidate_modules",
    "classify_intent",
    "intent",
    "run_agent_workflow",
    "_apply_answer_strategy_metadata",
    "_apply_answer_strategy_render_gate",
    "spec",
    "price",
    "logistics",
    "quality",
    "escalation",
)


def main() -> int:
    """Inspect selected_module flow."""

    print("=" * 80)
    print("inspecting Phase 3-I-I workflow selected_module flow")

    errors: list[str] = []

    result = {
        "workflow": inspect_file(path=WORKFLOW_FILE, errors=errors),
        "state": inspect_file(path=STATE_FILE, errors=errors),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I workflow selected_module flow inspection failed")
        return 1

    print("Phase 3-I-I workflow selected_module flow inspection passed")
    return 0


def inspect_file(
    *,
    path: Path,
    errors: list[str],
) -> dict[str, object]:
    """Inspect one source file."""

    if not path.exists():
        errors.append(f"missing file: {path}")
        return {"exists": False, "path": str(path)}

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    return {
        "exists": True,
        "path": str(path.relative_to(BACKEND_ROOT)),
        "line_count": len(lines),
        "matched_lines": extract_lines(lines=lines, anchors=ANCHORS, limit=260),
        "function_windows": {
            name: window
            for name, window in build_function_windows(lines=lines).items()
            if should_keep_window(window)
        },
    }


def extract_lines(
    *,
    lines: list[str],
    anchors: tuple[str, ...],
    limit: int,
) -> list[str]:
    """Extract lines containing anchors."""

    matched: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        lowered = line.lower()

        if any(anchor.lower() in lowered for anchor in anchors):
            matched.append(f"{line_number}: {line.rstrip()}")

    return matched[:limit]


def build_function_windows(
    *,
    lines: list[str],
) -> dict[str, list[str]]:
    """Build windows around function definitions containing relevant anchors."""

    windows: dict[str, list[str]] = {}

    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if not stripped.startswith("def ") and not stripped.startswith("async def "):
            continue

        function_name = stripped.split("(", 1)[0].replace("def ", "").replace(
            "async ", ""
        )

        start = max(index - 8, 1)
        end = min(index + 90, len(lines))

        window = [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ]

        windows[function_name] = window

    return windows


def should_keep_window(
    window: list[str],
) -> bool:
    """Return whether function window is relevant."""

    text = "\n".join(window).lower()

    return any(anchor.lower() in text for anchor in ANCHORS)


if __name__ == "__main__":
    raise SystemExit(main())