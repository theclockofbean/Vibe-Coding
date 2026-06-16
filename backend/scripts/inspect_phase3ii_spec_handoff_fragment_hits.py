"""Inspect exact handoff fragment hits for Phase 3-I-I spec interruptions."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final

JsonDict = dict[str, Any]

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CONFIG_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)

TARGET_QUERIES: Final[dict[str, str]] = {
    "TC_SPEC_003": "SKU003真皮那款有锥度要求吗 怎么安装",
    "TC_SPEC_006": "SKU011适配宝马那款 螺纹和锥度是多少",
    "TC_SPEC_007": "你们最长的杆是多少 哪款",
    "TC_SPEC_013": "SKU064带温控加热的球头 螺纹是多少 USB接口怎么用",
    "TC_SPEC_019": "SKU022铝合金梯形球头 有锥度要求吗",
    "TC_SPEC_021": "你们有没有M14螺纹的球头",
}


def main() -> int:
    """Inspect fragment hits."""

    print("=" * 80)
    print("inspecting Phase 3-I-I spec handoff fragment hits")

    errors: list[str] = []

    if not CONFIG_FILE.exists():
        errors.append(f"missing config file: {CONFIG_FILE}")
        pprint({"errors": errors})
        return 1

    config: JsonDict = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    fragments = extract_handoff_fragments(config)

    case_hits = {
        case_id: {
            "query": query,
            "hits": [
                fragment
                for fragment in fragments
                if fragment and fragment in query
            ],
        }
        for case_id, query in TARGET_QUERIES.items()
    }

    result = {
        "config_file": str(CONFIG_FILE.relative_to(PROJECT_ROOT)),
        "handoff_fragment_count": len(fragments),
        "handoff_fragments": fragments,
        "case_hits": case_hits,
        "proposed_classification": classify_hits(case_hits),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I spec handoff fragment hit inspection failed")
        return 1

    print("Phase 3-I-I spec handoff fragment hit inspection passed")
    return 0


def extract_handoff_fragments(config: JsonDict) -> list[str]:
    """Extract handoff risk fragments from strategy config."""

    raw_fragments = config.get("handoff_risk_fragments")

    if not isinstance(raw_fragments, list):
        return []

    return [
        str(item).strip()
        for item in raw_fragments
        if str(item).strip()
    ]


def classify_hits(
    case_hits: dict[str, JsonDict],
) -> dict[str, str]:
    """Classify each case for next patch decision."""

    classification: dict[str, str] = {}

    for case_id, item in case_hits.items():
        hits = item.get("hits")
        hit_set = set(hits if isinstance(hits, list) else [])

        if case_id == "TC_SPEC_007":
            classification[case_id] = "split_false_positive_or_structured_query_gap"
            continue

        if hit_set <= {"锥度", "M14"}:
            classification[case_id] = "safe_spec_attribute_should_not_handoff"
            continue

        if hit_set & {"安装", "适配", "宝马", "USB接口怎么用", "USB"}:
            classification[case_id] = (
                "mixed_spec_plus_risk_should_answer_specs_with_boundary_note"
            )
            continue

        classification[case_id] = "needs_manual_review"

    return classification


if __name__ == "__main__":
    raise SystemExit(main())