"""Check Phase 3-I-F machine-readable conflict cases JSON."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
JSON_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.json"
)

EXPECTED_CASE_COUNT: Final[int] = 15
ALLOWED_EXPECTED_MODULES: Final[set[str]] = {"price", "spec", "logistics"}
KNOWN_MODULES: Final[set[str]] = {"quality", "logistics", "price", "spec"}

EXPECTED_COLLECTIONS: Final[dict[str, str]] = {
    "quality": "quality_kb_v1",
    "logistics": "logistics_kb_v1",
    "price": "price_kb_v1",
    "spec": "spec_kb_v1",
}

EXPECTED_SOURCES: Final[dict[str, str]] = {
    "quality": "real_quality_kb",
    "logistics": "real_logistics_kb",
    "price": "real_price_kb",
    "spec": "real_spec_kb",
}

REQUIRED_METADATA_KEYS: Final[set[str]] = {
    "retrieval_selected_module",
    "retrieval_source",
    "retrieval_collection_name",
    "retrieval_hit_count",
}

REQUIRED_CONFLICT_TYPES: Final[set[str]] = {
    "price_spec",
    "spec_logistics",
    "spec_quality",
    "price_logistics",
    "logistics_quality",
    "price_quality",
    "logistics_spec",
    "spec_price",
}

REQUIRED_FORBIDDEN_FRAGMENTS: Final[set[str]] = {
    "最低价给你",
    "全网最低",
    "一定包邮",
    "今天一定发",
    "明天一定到",
    "三天必到",
    "万能适配",
    "百分百适配",
    "一定适配",
    "保证适配",
    "永不生锈",
    "十万公里没问题",
    "一定赔",
    "一定补发",
}


def main() -> int:
    """Run JSON check."""

    print("=" * 80)
    print("checking Phase 3-I-F conflict cases JSON")

    errors: list[str] = []

    if not JSON_FILE.exists():
        errors.append(f"missing JSON file: {JSON_FILE}")
        pprint({"errors": errors})
        return 1

    data = load_json_file()
    validate_top_level(data=data, errors=errors)
    cases = cast(list[dict[str, Any]], data.get("cases", []))
    validate_cases(cases=cases, errors=errors)

    result = {
        "json_file": str(JSON_FILE),
        "case_count": len(cases),
        "expected_case_count": EXPECTED_CASE_COUNT,
        "expected_modules": sorted(
            {
                str(case.get("expected_module"))
                for case in cases
                if case.get("expected_module")
            }
        ),
        "conflict_types": sorted(
            {
                str(case.get("conflict_type"))
                for case in cases
                if case.get("conflict_type")
            }
        ),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-F conflict cases JSON check failed")
        return 1

    print("Phase 3-I-F conflict cases JSON check passed")
    return 0


def load_json_file() -> dict[str, Any]:
    """Load JSON file."""

    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")

    return cast(dict[str, Any], data)


def validate_top_level(
    *,
    data: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate top-level JSON fields."""

    if data.get("phase") != "Phase 3-I-F":
        errors.append("phase must be Phase 3-I-F")

    metadata_requirements = set(
        str(item)
        for item in data.get("metadata_requirements", [])
    )

    missing_metadata_keys = REQUIRED_METADATA_KEYS - metadata_requirements

    if missing_metadata_keys:
        errors.append(f"missing metadata requirements: {sorted(missing_metadata_keys)}")

    module_collections = cast(dict[str, Any], data.get("module_collections", {}))
    module_sources = cast(dict[str, Any], data.get("module_sources", {}))

    for module, collection_name in EXPECTED_COLLECTIONS.items():
        if module_collections.get(module) != collection_name:
            errors.append(f"{module}: collection must be {collection_name}")

    for module, source_name in EXPECTED_SOURCES.items():
        if module_sources.get(module) != source_name:
            errors.append(f"{module}: source must be {source_name}")

    forbidden_fragments = set(
        str(item)
        for item in data.get("forbidden_response_fragments", [])
    )

    missing_forbidden = REQUIRED_FORBIDDEN_FRAGMENTS - forbidden_fragments

    if missing_forbidden:
        errors.append(f"missing forbidden fragments: {sorted(missing_forbidden)}")


def validate_cases(
    *,
    cases: list[dict[str, Any]],
    errors: list[str],
) -> None:
    """Validate case list."""

    if len(cases) != EXPECTED_CASE_COUNT:
        errors.append(f"expected {EXPECTED_CASE_COUNT} cases, got {len(cases)}")

    case_ids = [str(case.get("case_id", "")) for case in cases]

    expected_case_ids = [
        f"CONFLICT_{index:03d}"
        for index in range(1, EXPECTED_CASE_COUNT + 1)
    ]

    if case_ids != expected_case_ids:
        errors.append(f"case_id sequence mismatch: {case_ids}")

    if len(case_ids) != len(set(case_ids)):
        errors.append("duplicated case_id found")

    conflict_types = set()

    for case in cases:
        validate_one_case(case=case, errors=errors)
        conflict_type = str(case.get("conflict_type", ""))
        if conflict_type:
            conflict_types.add(conflict_type)

    missing_conflict_types = REQUIRED_CONFLICT_TYPES - conflict_types

    if missing_conflict_types:
        errors.append(f"missing conflict types: {sorted(missing_conflict_types)}")


def validate_one_case(
    *,
    case: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate one case."""

    case_id = str(case.get("case_id", "<missing>"))
    query = str(case.get("query", "")).strip()
    expected_module = str(case.get("expected_module", "")).strip()
    conflict_type = str(case.get("conflict_type", "")).strip()
    risk_tags = case.get("risk_tags", [])
    reason = str(case.get("reason", "")).strip()

    if not query:
        errors.append(f"{case_id}: query is empty")

    if expected_module not in ALLOWED_EXPECTED_MODULES:
        errors.append(f"{case_id}: unexpected expected_module: {expected_module}")

    if conflict_type not in REQUIRED_CONFLICT_TYPES:
        errors.append(f"{case_id}: unexpected conflict_type: {conflict_type}")

    modules_in_conflict = set(conflict_type.split("_"))

    if not modules_in_conflict <= KNOWN_MODULES:
        errors.append(f"{case_id}: unknown modules in conflict_type: {conflict_type}")

    if expected_module and expected_module not in modules_in_conflict:
        errors.append(
            f"{case_id}: expected_module {expected_module} not in {conflict_type}"
        )

    if not isinstance(risk_tags, list) or not risk_tags:
        errors.append(f"{case_id}: risk_tags must be non-empty list")

    if not reason:
        errors.append(f"{case_id}: reason is empty")


if __name__ == "__main__":
    raise SystemExit(main())