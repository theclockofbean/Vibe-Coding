"""Inspect remaining Phase 3-II spec failures."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
REPORT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs/evaluation/phase3ii_real_llm_50_case_eval_report.json"
)
OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs/diagnostics/phase3ii_remaining_spec_cases.json"
)

CASE_IDS: Final[set[str]] = {"TC_SPEC_007", "TC_SPEC_014", "TC_SPEC_021"}


def main() -> int:
    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    cases = extract_cases(report)

    selected = [
        case for case in cases
        if str(case.get("case_id")) in CASE_IDS
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    pprint(
        {
            "output_file": str(OUTPUT_FILE),
            "case_count": len(selected),
            "case_ids": [case.get("case_id") for case in selected],
        }
    )
    return 0


def extract_cases(report: Any) -> list[dict[str, Any]]:
    if isinstance(report, list):
        return [case for case in report if isinstance(case, dict)]

    if isinstance(report, dict):
        for key in ("cases", "results", "case_results", "evaluation_results"):
            value = report.get(key)
            if isinstance(value, list):
                return [case for case in value if isinstance(case, dict)]

    return []


if __name__ == "__main__":
    raise SystemExit(main())