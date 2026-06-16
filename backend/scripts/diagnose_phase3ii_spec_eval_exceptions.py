"""Diagnose spec evaluation fallback exceptions from the 50-case report."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

REPORT_FILE: Final[Path] = PROJECT_ROOT / "logs/evaluation/phase3ii_real_llm_50_case_eval_report.json"
OUTPUT_FILE: Final[Path] = PROJECT_ROOT / "logs/diagnostics/phase3ii_spec_eval_exception_diagnostics.json"


INTERESTING_KEYS: Final[tuple[str, ...]] = (
    "case_id",
    "query",
    "category",
    "selected_module",
    "expected_module",
    "passed",
    "failure_reasons",
    "final_response",
    "final_response_preview",
    "answer_text",
    "module_payload",
    "parsed_query",
    "handler_input",
    "handler_output",
    "spec_result",
    "structured_facts",
    "errors",
    "warnings",
    "fallback_reason",
    "render_warnings",
    "response_warnings",
    "risk_reasons",
    "risk_flags",
)


def main() -> int:
    """Export focused spec diagnostics."""

    print("=" * 80)
    print("diagnosing Phase 3-I-I spec eval exceptions")

    if not REPORT_FILE.exists():
        print(f"missing report file: {REPORT_FILE}")
        return 1

    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    cases = extract_cases(report)

    spec_cases = [
        case for case in cases
        if str(case.get("case_id", "")).startswith("TC_SPEC_")
    ]

    fallback_cases = [
        case for case in spec_cases
        if "系统处理当前问题时发生异常" in str(case.get("final_response", ""))
        or "系统处理当前问题时发生异常" in str(case.get("final_response_preview", ""))
    ]

    diagnostics: dict[str, Any] = {
        "report_file": str(REPORT_FILE),
        "total_case_count": len(cases),
        "spec_case_count": len(spec_cases),
        "spec_fallback_case_count": len(fallback_cases),
        "spec_case_ids": [case.get("case_id") for case in spec_cases],
        "spec_fallback_case_ids": [case.get("case_id") for case in fallback_cases],
        "fallback_cases": [
            compact_case(case)
            for case in fallback_cases
        ],
        "first_spec_cases": [
            compact_case(case)
            for case in spec_cases[:8]
        ],
        "report_top_level_keys": sorted(report) if isinstance(report, dict) else [],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pprint(
        {
            "output_file": str(OUTPUT_FILE),
            "total_case_count": len(cases),
            "spec_case_count": len(spec_cases),
            "spec_fallback_case_count": len(fallback_cases),
            "spec_fallback_case_ids": diagnostics["spec_fallback_case_ids"],
        }
    )

    print("Phase 3-I-I spec eval exception diagnostics exported")
    return 0


def extract_cases(report: Any) -> list[dict[str, Any]]:
    """Extract case list from flexible report structure."""

    if isinstance(report, list):
        return [case for case in report if isinstance(case, dict)]

    if not isinstance(report, dict):
        return []

    for key in ("cases", "results", "case_results", "evaluation_results", "failed_cases"):
        value = report.get(key)

        if isinstance(value, list):
            return [case for case in value if isinstance(case, dict)]

    all_cases: list[dict[str, Any]] = []

    for value in report.values():
        if isinstance(value, list):
            all_cases.extend(item for item in value if isinstance(item, dict) and "case_id" in item)

    return all_cases


def compact_case(case: dict[str, Any]) -> dict[str, Any]:
    """Keep important fields and nested diagnostic hints."""

    compact: dict[str, Any] = {}

    for key in INTERESTING_KEYS:
        if key in case:
            compact[key] = shorten(case[key])

    for key, value in case.items():
        if isinstance(value, dict) and any(
            token in key.lower()
            for token in ("state", "debug", "trace", "module", "handler", "parser", "render")
        ):
            compact[key] = shorten(value)

    return compact


def shorten(value: Any, *, limit: int = 1800) -> Any:
    """Shorten long strings recursively."""

    if isinstance(value, str):
        if len(value) <= limit:
            return value
        return value[:limit] + "...<truncated>"

    if isinstance(value, list):
        return [shorten(item, limit=limit) for item in value[:20]]

    if isinstance(value, dict):
        return {
            str(key): shorten(item, limit=limit)
            for key, item in list(value.items())[:80]
        }

    return value


if __name__ == "__main__":
    raise SystemExit(main())