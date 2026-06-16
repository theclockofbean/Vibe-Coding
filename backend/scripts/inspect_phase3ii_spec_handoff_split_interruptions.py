"""Inspect Phase 3-I-I spec handoff/split interruption cases."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final

JsonDict = dict[str, Any]

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
REPORT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs/evaluation/phase3ii_real_llm_50_case_eval_report.json"
)
ANSWER_STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)
STRATEGY_CONFIG_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)

TARGET_CASE_IDS: Final[set[str]] = {
    "TC_SPEC_003",
    "TC_SPEC_006",
    "TC_SPEC_007",
    "TC_SPEC_013",
    "TC_SPEC_019",
    "TC_SPEC_021",
}


def main() -> int:
    """Inspect interruption causes."""

    print("=" * 80)
    print("inspecting Phase 3-I-I spec handoff/split interruption cases")

    errors: list[str] = []

    if not REPORT_FILE.exists():
        errors.append(f"missing report file: {REPORT_FILE}")
        pprint({"errors": errors})
        return 1

    report: JsonDict = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    results = collect_results(report)
    target_results = [
        result
        for result in results
        if str(result.get("case_id") or "") in TARGET_CASE_IDS
    ]

    if len(target_results) != len(TARGET_CASE_IDS):
        errors.append(
            f"expected {len(TARGET_CASE_IDS)} target cases, got {len(target_results)}"
        )

    result = {
        "report_file": str(REPORT_FILE),
        "target_case_count": len(target_results),
        "target_cases": [build_case_view(item) for item in target_results],
        "strategy_source_hits": inspect_strategy_source(),
        "strategy_config_hits": inspect_strategy_config(),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I spec interruption inspection failed")
        return 1

    print("Phase 3-I-I spec interruption inspection passed")
    return 0


def collect_results(report: JsonDict) -> list[JsonDict]:
    """Collect full results from report."""

    results = report.get("results")
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]

    summary = report.get("summary")
    if isinstance(summary, dict):
        failed_cases = summary.get("failed_cases")
        if isinstance(failed_cases, list):
            return [item for item in failed_cases if isinstance(item, dict)]

    failed_cases = report.get("failed_cases")
    if isinstance(failed_cases, list):
        return [item for item in failed_cases if isinstance(item, dict)]

    return []


def build_case_view(result: JsonDict) -> JsonDict:
    """Build compact diagnostic case view."""

    return {
        "case_id": result.get("case_id"),
        "query": result.get("query"),
        "category": result.get("category"),
        "scenario_type": result.get("scenario_type"),
        "expected_module": result.get("expected_module"),
        "selected_module": result.get("selected_module"),
        "effective_selected_module": result.get("effective_selected_module"),
        "answer_strategy_mode": result.get("answer_strategy_mode"),
        "answer_primary_module": result.get("answer_primary_module"),
        "answer_candidate_modules": result.get("answer_candidate_modules"),
        "handoff_required": result.get("handoff_required"),
        "answer_handoff_required": result.get("answer_handoff_required"),
        "answer_safety_blocked": result.get("answer_safety_blocked"),
        "render_safety_blocked": result.get("render_safety_blocked"),
        "risk_flags": result.get("risk_flags"),
        "response_warnings": result.get("response_warnings"),
        "retrieved_chunk_count": result.get("retrieved_chunk_count"),
        "render_mode": result.get("render_mode"),
        "failure_reasons": result.get("failure_reasons"),
        "final_response_preview": str(result.get("final_response") or "")[:360],
    }


def inspect_strategy_source() -> JsonDict:
    """Inspect source file for handoff/split related logic."""

    if not ANSWER_STRATEGY_FILE.exists():
        return {"error": f"missing {ANSWER_STRATEGY_FILE}"}

    lines = ANSWER_STRATEGY_FILE.read_text(encoding="utf-8").splitlines()

    anchors = (
        "handoff_required",
        "split_required",
        "HANDOFF",
        "SPLIT",
        "detect_handoff",
        "handoff_risk_fragments",
        "source_group",
        "multi",
        "USB",
        "M14",
        "锥度",
        "人工确认",
    )

    matched: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        lowered = line.lower()

        if any(anchor.lower() in lowered for anchor in anchors):
            matched.append(f"{line_number}: {line.rstrip()}")

    return {
        "file": str(ANSWER_STRATEGY_FILE.relative_to(BACKEND_ROOT)),
        "matched_lines": matched[:220],
    }


def inspect_strategy_config() -> JsonDict:
    """Inspect strategy JSON config for handoff/split fragments."""

    if not STRATEGY_CONFIG_FILE.exists():
        return {"error": f"missing {STRATEGY_CONFIG_FILE}"}

    config = json.loads(STRATEGY_CONFIG_FILE.read_text(encoding="utf-8"))

    serialized = json.dumps(config, ensure_ascii=False, indent=2)

    focus_terms = [
        "handoff_risk_fragments",
        "split",
        "USB",
        "M14",
        "锥度",
        "人工确认",
        "1:10",
        "1:15",
        "最长",
        "杆长",
    ]

    hits: dict[str, bool] = {
        term: term in serialized
        for term in focus_terms
    }

    return {
        "file": str(STRATEGY_CONFIG_FILE.relative_to(PROJECT_ROOT)),
        "focus_term_presence": hits,
    }


if __name__ == "__main__":
    raise SystemExit(main())