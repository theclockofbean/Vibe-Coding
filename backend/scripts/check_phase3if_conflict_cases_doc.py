"""Check Phase 3-I-F cross-module conflict cases doc."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DOC_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.md"
)

REQUIRED_CASE_IDS: Final[tuple[str, ...]] = tuple(
    f"CONFLICT_{index:03d}"
    for index in range(1, 16)
)

REQUIRED_EXPECTED_MODULES: Final[tuple[str, ...]] = (
    "price",
    "spec",
    "logistics",
)

REQUIRED_MENTIONED_MODULES: Final[tuple[str, ...]] = (
    "Quality",
    "quality",
)

REQUIRED_CONFLICT_TYPES: Final[tuple[str, ...]] = (
    "price_spec",
    "spec_logistics",
    "spec_quality",
    "price_logistics",
    "logistics_quality",
    "price_quality",
    "logistics_spec",
)

FORBIDDEN_OUTPUT_FRAGMENTS: Final[tuple[str, ...]] = (
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
)


def main() -> int:
    """Run conflict cases doc check."""

    print("=" * 80)
    print("checking Phase 3-I-F conflict cases doc")

    errors: list[str] = []

    if not DOC_FILE.exists():
        errors.append(f"missing doc file: {DOC_FILE}")
        pprint({"errors": errors})
        return 1

    content = DOC_FILE.read_text(encoding="utf-8")

    for case_id in REQUIRED_CASE_IDS:
        if case_id not in content:
            errors.append(f"missing case_id: {case_id}")

    for module in REQUIRED_EXPECTED_MODULES:
        if f"| {module} |" not in content:
            errors.append(f"missing expected module in table: {module}")

    for module in REQUIRED_MENTIONED_MODULES:
        if module not in content:
            errors.append(f"missing mentioned module: {module}")

    for conflict_type in REQUIRED_CONFLICT_TYPES:
        if conflict_type not in content:
            errors.append(f"missing conflict type: {conflict_type}")

    for fragment in FORBIDDEN_OUTPUT_FRAGMENTS:
        if fragment not in content:
            errors.append(f"missing forbidden fragment: {fragment}")

    result = {
        "doc_file": str(DOC_FILE),
        "exists": DOC_FILE.exists(),
        "case_count": len(REQUIRED_CASE_IDS),
        "expected_module_count": len(REQUIRED_EXPECTED_MODULES),
        "mentioned_module_count": len(REQUIRED_MENTIONED_MODULES),
        "conflict_type_count": len(REQUIRED_CONFLICT_TYPES),
        "forbidden_fragment_count": len(FORBIDDEN_OUTPUT_FRAGMENTS),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-F conflict cases doc check failed")
        return 1

    print("Phase 3-I-F conflict cases doc check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())