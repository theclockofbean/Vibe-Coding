"""Analyze Phase 3-I-I P1 spec failures after routing fix."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final

JsonDict = dict[str, Any]

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
REPORT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs/evaluation/phase3ii_real_llm_50_case_eval_report.json"
)


def main() -> int:
    """Analyze spec failures."""

    print("=" * 80)
    print("analyzing Phase 3-I-I P1 spec failures")

    errors: list[str] = []

    if not REPORT_FILE.exists():
        errors.append(f"missing report file: {REPORT_FILE}")
        pprint({"errors": errors})
        return 1

    report: JsonDict = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    failed_cases = collect_failed_cases(report)

    if not failed_cases:
        errors.append(
            "no failed cases found; report schema may have changed or "
            "evaluation report was not refreshed"
        )

    spec_cases = [
        case
        for case in failed_cases
        if str(case.get("category") or "") == "spec"
    ]

    buckets: dict[str, list[JsonDict]] = {
        "format_only_candidates": [],
        "structured_query_gap": [],
        "handoff_or_split_interruption": [],
        "module_mismatch_remaining": [],
        "other_spec": [],
    }

    for case in spec_cases:
        item = build_case_item(case)

        reasons = item["reasons"]
        strategy = str(item["strategy"])
        final_response = str(item["final_preview"])

        if any("selected_module expected" in reason for reason in reasons):
            buckets["module_mismatch_remaining"].append(item)
            continue

        if strategy in {"handoff_required", "split_required"}:
            buckets["handoff_or_split_interruption"].append(item)
            continue

        if looks_like_format_only(
            reasons=reasons,
            final_response=final_response,
        ):
            buckets["format_only_candidates"].append(item)
            continue

        if looks_like_structured_query_gap(
            reasons=reasons,
            final_response=final_response,
        ):
            buckets["structured_query_gap"].append(item)
            continue

        buckets["other_spec"].append(item)

    result = {
        "report_file": str(REPORT_FILE),
        "failed_case_count_detected": len(failed_cases),
        "spec_failed_count": len(spec_cases),
        "bucket_counts": {key: len(value) for key, value in buckets.items()},
        "bucket_case_ids": {
            key: [str(item["case_id"]) for item in value]
            for key, value in buckets.items()
        },
        "buckets": buckets,
        "recommended_order": [
            (
                "P1-A renderer/evaluator numeric normalization: "
                "55.00 mm should satisfy 55mm; 40.00 mm should satisfy 40mm."
            ),
            (
                "P1-B spec structured query service: support attribute, range, "
                "list, max rod length, and ball diameter queries."
            ),
            (
                "P1-C reduce false handoff or split for safe spec queries "
                "after selected module is spec."
            ),
            "P1-D handle residual module mismatch only if any remains.",
        ],
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I P1 spec failure analysis failed")
        return 1

    print("Phase 3-I-I P1 spec failure analysis passed")
    return 0


def collect_failed_cases(report: JsonDict) -> list[JsonDict]:
    """Collect failed cases from possible report schemas."""

    top_level = report.get("failed_cases")
    if isinstance(top_level, list) and top_level:
        return [case for case in top_level if isinstance(case, dict)]

    summary = report.get("summary")
    if isinstance(summary, dict):
        summary_failed = summary.get("failed_cases")
        if isinstance(summary_failed, list) and summary_failed:
            return [case for case in summary_failed if isinstance(case, dict)]

    case_results = report.get("case_results")
    if isinstance(case_results, list) and case_results:
        return [
            case
            for case in case_results
            if isinstance(case, dict)
            and (
                case.get("passed") is not True
                or bool(case.get("failure_reasons"))
            )
        ]

    results = report.get("results")
    if isinstance(results, list) and results:
        return [
            case
            for case in results
            if isinstance(case, dict)
            and (
                case.get("passed") is not True
                or bool(case.get("failure_reasons"))
            )
        ]

    return []


def build_case_item(case: JsonDict) -> JsonDict:
    """Build normalized case item."""

    reasons = [
        str(reason)
        for reason in case.get("failure_reasons", [])
        if isinstance(reason, str)
    ]

    return {
        "case_id": str(case.get("case_id") or ""),
        "strategy": str(case.get("answer_strategy_mode") or ""),
        "expected_module": case.get("expected_module"),
        "selected_module": case.get("selected_module"),
        "effective_selected_module": case.get("effective_selected_module"),
        "reasons": reasons,
        "final_preview": str(case.get("final_response_preview") or "")[:320],
    }


def looks_like_format_only(
    *,
    reasons: list[str],
    final_response: str,
) -> bool:
    """Return whether failure appears to be formatting only."""

    missing_values = extract_missing_fragments(reasons)

    if not missing_values:
        return False

    normalized_response = normalize_for_format_compare(final_response)

    for value in missing_values:
        normalized_value = normalize_for_format_compare(value)

        if normalized_value and normalized_value in normalized_response:
            continue

        return False

    return True


def looks_like_structured_query_gap(
    *,
    reasons: list[str],
    final_response: str,
) -> bool:
    """Return whether failure looks like missing structured query capability."""

    final_lower = final_response.lower()

    if "no sku id" in final_lower:
        return True

    if "当前只支持按sku" in final_lower.replace(" ", ""):
        return True

    missing_values = extract_missing_fragments(reasons)
    sku_missing_count = sum(1 for value in missing_values if value.startswith("SKU"))

    if sku_missing_count >= 2:
        return True

    thread_specs = {"M8×1.25", "M10×1.5", "M12×1.25", "M14"}
    if any(value in thread_specs for value in missing_values):
        return True

    return False


def extract_missing_fragments(
    reasons: list[str],
) -> list[str]:
    """Extract missing fragments from failure reasons."""

    fragments: list[str] = []
    marker = "fragment: "

    for reason in reasons:
        if marker not in reason:
            continue

        fragments.append(reason.split(marker, 1)[1].strip())

    return fragments


def normalize_for_format_compare(value: str) -> str:
    """Normalize numeric formatting for comparison."""

    normalized = value.replace(" ", "")
    normalized = normalized.replace("毫米", "mm")
    normalized = normalized.replace("MM", "mm")
    normalized = normalized.replace(".00mm", "mm")
    normalized = normalized.replace(".0mm", "mm")

    return normalized


if __name__ == "__main__":
    raise SystemExit(main())