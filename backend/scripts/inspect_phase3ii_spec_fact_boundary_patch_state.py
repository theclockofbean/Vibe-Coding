"""Inspect current spec fact boundary patch state."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)


def main() -> int:
    """Inspect strategy source patch state."""

    print("=" * 80)
    print("inspecting Phase 3-I-I spec fact boundary patch state")

    errors: list[str] = []

    if not STRATEGY_FILE.exists():
        errors.append(f"missing strategy file: {STRATEGY_FILE}")
        pprint({"errors": errors})
        return 1

    lines = STRATEGY_FILE.read_text(encoding="utf-8").splitlines()

    result = {
        "string_presence": {
            "should_answer_spec_fact_with_risk_boundary": contains(
                lines,
                "should_answer_spec_fact_with_risk_boundary",
            ),
            "spec fact answer with risk boundary": contains(
                lines,
                "spec fact answer with risk boundary",
            ),
            "strategy_mode": contains(lines, "strategy_mode="),
            "mode_keyword": contains(lines, "mode="),
            "HANDOFF_MODE": contains(lines, "HANDOFF_MODE"),
        },
        "decide_answer_strategy_window": extract_window(
            lines,
            "def decide_answer_strategy(",
            before=5,
            after=95,
        ),
        "helper_window": extract_window(
            lines,
            "def should_answer_spec_fact_with_risk_boundary(",
            before=5,
            after=80,
        ),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I spec fact boundary patch state inspection failed")
        return 1

    print("Phase 3-I-I spec fact boundary patch state inspection passed")
    return 0


def contains(
    lines: list[str],
    needle: str,
) -> bool:
    """Return whether needle exists."""

    return any(needle in line for line in lines)


def extract_window(
    lines: list[str],
    needle: str,
    *,
    before: int,
    after: int,
) -> list[str]:
    """Extract source window around first needle."""

    for index, line in enumerate(lines, start=1):
        if needle not in line:
            continue

        start = max(1, index - before)
        end = min(len(lines), index + after)

        return [
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(start, end + 1)
        ]

    return []


if __name__ == "__main__":
    raise SystemExit(main())