"""Analyze Phase 3-I-I major failures after blocker gate reached zero."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from pprint import pprint
from typing import Any, Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

REPORT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs/evaluation/phase3ii_real_llm_50_case_eval_report.json"
)

MAJOR_PREFIX: Final[str] = "MAJOR"
BLOCKER_PREFIX: Final[str] = "BLOCKER"


def main() -> int:
    """Analyze major-only failures."""

    print("=" * 80)
    print("analyzing Phase 3-I-I major failures")

    if not REPORT_FILE.exists():
        print(f"missing report file: {REPORT_FILE}")
        return 1

    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    results = report.get("results", [])

    if not isinstance(results, list):
        print("report.results must be list")
        return 1

    failed_major_cases = [
        item
        for item in results
        if isinstance(item, dict)
        and has_major(item)
        and not has_blocker(item)
    ]

    result = {
        "summary": report.get("summary", {}),
        "major_only_count": len(failed_major_cases),
        "by_category": Counter(str(item.get("category")) for item in failed_major_cases),
        "by_selected_module": Counter(
            str(item.get("selected_module")) for item in failed_major_cases
        ),
        "by_strategy_mode": Counter(
            str(item.get("answer_strategy_mode")) for item in failed_major_cases
        ),
        "major_reason_buckets": bucket_major_reasons(failed_major_cases),
        "candidate_fix_order": build_candidate_fix_order(failed_major_cases),
        "representative_cases": build_representative_cases(failed_major_cases),
    }

    pprint(result)

    print("Phase 3-I-I major failure analysis completed")
    return 0


def has_major(item: dict[str, Any]) -> bool:
    """Return whether result has major reason."""

    return any(
        str(reason).startswith(MAJOR_PREFIX)
        for reason in item.get("failure_reasons", [])
    )


def has_blocker(item: dict[str, Any]) -> bool:
    """Return whether result has blocker reason."""

    return any(
        str(reason).startswith(BLOCKER_PREFIX)
        for reason in item.get("failure_reasons", [])
    )


def bucket_major_reasons(
    cases: list[dict[str, Any]],
) -> dict[str, int]:
    """Bucket major reasons."""

    buckets: Counter[str] = Counter()

    for item in cases:
        reasons = [str(reason) for reason in item.get("failure_reasons", [])]

        for reason in reasons:
            if "selected_module expected" in reason:
                buckets["module_mismatch"] += 1
            elif "missing must_contain_all" in reason:
                buckets["missing_must_contain_all"] += 1
            elif "missing any of must_contain_any" in reason:
                buckets["missing_must_contain_any"] += 1
            elif "price" in reason.lower():
                buckets["price_quality_assertion"] += 1
            else:
                buckets["other_major"] += 1

    return dict(buckets)


def build_candidate_fix_order(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build fix order by impact."""

    grouped: dict[str, list[str]] = defaultdict(list)

    for item in cases:
        case_id = str(item.get("case_id"))
        category = str(item.get("category"))
        selected_module = str(item.get("selected_module"))
        reasons = [str(reason) for reason in item.get("failure_reasons", [])]

        if any("selected_module expected" in reason for reason in reasons):
            grouped["P0_module_routing"].append(case_id)
        elif category == "spec" and any(
            "missing must_contain_all" in reason for reason in reasons
        ):
            grouped["P1_spec_parser_or_renderer_format"].append(case_id)
        elif category == "logistics":
            grouped["P2_logistics_renderer_contract"].append(case_id)
        elif category == "quality":
            grouped["P3_quality_renderer_contract"].append(case_id)
        elif category == "price":
            grouped["P4_price_renderer_contract"].append(case_id)
        elif category == "escalation":
            grouped["P5_escalation_capability_gap"].append(case_id)
        else:
            grouped[f"P9_other_{selected_module}"].append(case_id)

    return [
        {
            "bucket": bucket,
            "count": len(case_ids),
            "case_ids": case_ids,
        }
        for bucket, case_ids in sorted(grouped.items())
    ]


def build_representative_cases(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return compact representative cases."""

    representatives: list[dict[str, Any]] = []

    for item in cases[:20]:
        representatives.append(
            {
                "case_id": item.get("case_id"),
                "category": item.get("category"),
                "scenario_type": item.get("scenario_type"),
                "expected_module": item.get("expected_module"),
                "selected_module": item.get("selected_module"),
                "strategy": item.get("answer_strategy_mode"),
                "reasons": item.get("failure_reasons", [])[:5],
                "final": str(item.get("final_response_preview") or "")[:300],
            }
        )

    return representatives


if __name__ == "__main__":
    raise SystemExit(main())