"""Inspect renderer entrypoints before Phase 3-I-G8 patching."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
APP_ROOT: Final[Path] = BACKEND_ROOT / "app"

SEARCH_PATTERNS: Final[tuple[str, ...]] = (
    "grounded",
    "render",
    "final_response",
    "safety_blocked",
    "render_mode",
    "render_safety_blocked",
    "render_is_grounded",
    "answer_strategy_mode",
)

CANDIDATE_FILE_KEYWORDS: Final[tuple[str, ...]] = (
    "render",
    "renderer",
    "workflow",
    "answer",
)


def main() -> int:
    """Inspect possible renderer entrypoints."""

    print("=" * 80)
    print("inspecting Phase 3-I-G renderer entrypoints")

    if not APP_ROOT.exists():
        pprint({"error": f"missing app root: {APP_ROOT}"})
        return 1

    candidates: list[dict[str, object]] = []

    for path in sorted(APP_ROOT.rglob("*.py")):
        if should_skip(path):
            continue

        content = path.read_text(encoding="utf-8")
        lowered_name = path.name.lower()
        matched_patterns = [
            pattern
            for pattern in SEARCH_PATTERNS
            if pattern in content
        ]

        if not matched_patterns:
            continue

        strong_name_match = any(
            keyword in lowered_name
            for keyword in CANDIDATE_FILE_KEYWORDS
        )

        function_lines = extract_function_lines(content=content)

        candidates.append(
            {
                "path": str(path.relative_to(BACKEND_ROOT)),
                "strong_name_match": strong_name_match,
                "matched_patterns": matched_patterns,
                "function_lines": function_lines[:20],
            }
        )

    workflow_file = BACKEND_ROOT / "app/agent/workflow.py"
    workflow_snippets = inspect_workflow_renderer_context(workflow_file)

    result = {
        "candidate_count": len(candidates),
        "candidates": candidates,
        "workflow_renderer_context": workflow_snippets,
    }

    pprint(result)

    if not candidates:
        print("Phase 3-I-G renderer entrypoint inspection failed: no candidates")
        return 1

    print("Phase 3-I-G renderer entrypoint inspection completed")
    return 0


def should_skip(path: Path) -> bool:
    """Return whether file should be skipped."""

    parts = set(path.parts)

    return bool(
        "__pycache__" in parts
        or ".venv" in parts
        or "site-packages" in parts
    )


def extract_function_lines(
    *,
    content: str,
) -> list[str]:
    """Extract function or class definition lines."""

    lines: list[str] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()

        if stripped.startswith(("def ", "async def ", "class ")):
            lines.append(f"{line_number}: {stripped}")

    return lines


def inspect_workflow_renderer_context(
    workflow_file: Path,
) -> list[str]:
    """Inspect workflow render-related context."""

    if not workflow_file.exists():
        return [f"missing workflow file: {workflow_file}"]

    lines = workflow_file.read_text(encoding="utf-8").splitlines()
    snippets: list[str] = []

    for index, line in enumerate(lines, start=1):
        lowered = line.lower()

        if (
            "render" in lowered
            or "final_response" in lowered
            or "grounded" in lowered
            or "safety_blocked" in lowered
        ):
            start = max(1, index - 2)
            end = min(len(lines), index + 2)
            snippets.append(
                "\n".join(
                    f"{line_no}: {lines[line_no - 1]}"
                    for line_no in range(start, end + 1)
                )
            )

    return snippets[:40]


if __name__ == "__main__":
    raise SystemExit(main())