"""Summarize Phase 3-I-I real LLM 50-case evaluation report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final


REPORT_FILE: Final[Path] = Path(
    "D:/Projects/ai-knowledge-agent-platform/logs/evaluation/"
    "phase3ii_real_llm_50_case_eval_report.json"
)


def main() -> int:
    """Print compact failure summary."""

    if not REPORT_FILE.exists():
        print(f"missing report file: {REPORT_FILE}")
        return 1

    data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))

    summary: dict[str, Any] = data["summary"]
    results: list[dict[str, Any]] = data["results"]

    print("SUMMARY")
    for key in [
        "total_cases",
        "blocker_count",
        "major_count",
        "workflow_error_count",
        "module_accuracy",
        "risk_gate_pass_rate",
        "final_response_non_empty_rate",
        "forbidden_commitment_leak_count",
        "price_violation_count",
        "price_compliance_rate",
        "failed_case_count",
    ]:
        print(f"{key}: {summary.get(key)}")

    print("\nBLOCKER CASES")
    for item in results:
        blockers = [
            reason
            for reason in item["failure_reasons"]
            if str(reason).startswith("BLOCKER")
        ]

        if not blockers:
            continue

        print("=" * 80)
        print(item["case_id"], item["category"], item["scenario_type"])
        print("expected:", item["expected_module"], "selected:", item["selected_module"])
        print("strategy:", item["answer_strategy_mode"])
        print("blockers:", blockers)
        print("final:", str(item["final_response"])[:500])

    print("\nTOP MAJOR CASES")
    count = 0

    for item in results:
        majors = [
            reason
            for reason in item["failure_reasons"]
            if str(reason).startswith("MAJOR")
        ]

        if not majors:
            continue

        count += 1

        if count > 10:
            break

        print("=" * 80)
        print(item["case_id"], item["category"], item["scenario_type"])
        print("expected:", item["expected_module"], "selected:", item["selected_module"])
        print("strategy:", item["answer_strategy_mode"])
        print("majors:", majors[:5])
        print("final:", str(item["final_response"])[:400])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())