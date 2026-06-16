"""Check Phase 3-I-I real LLM 50-case evaluation gate design."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Any, Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DOC_FILE: Final[Path] = (
    PROJECT_ROOT
    / "docs/backend/phase3ii_real_llm_50_case_eval_gate_design_v0.1.md"
)
TEST_CASE_FILE: Final[Path] = PROJECT_ROOT / "test_cases_draft.xlsx"

REQUIRED_DOC_FRAGMENTS: Final[tuple[str, ...]] = (
    "Phase 3-I-I Real LLM 50-case Evaluation Gate Design v0.1",
    "price_compliance_rate = 100%",
    "forbidden_commitment_leak_count = 0",
    "module_accuracy >= 90%",
    "risk_gate_pass_rate",
    "final_response_non_empty_rate",
    "workflow_error_count",
    "Blocker",
    "Major",
    "Minor",
    "LLM 不是事实来源",
    "RAG 不是业务承诺来源",
)

REQUIRED_OUTPUT_FIELDS: Final[tuple[str, ...]] = (
    "case_id",
    "query",
    "category",
    "scenario_type",
    "expected_module",
    "selected_module",
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_safety_blocked",
    "answer_handoff_required",
    "final_response",
    "response_warnings",
    "risk_flags",
    "retrieved_chunk_count",
    "used_llm_output",
    "render_mode",
    "render_safety_blocked",
    "latency_ms",
    "passed",
    "failure_reasons",
)

FORBIDDEN_COMMITMENTS: Final[tuple[str, ...]] = (
    "一定包邮",
    "保证包邮",
    "今天一定发",
    "明天一定到",
    "保证到货",
    "保证适配",
    "百分百适配",
    "全网最低",
    "最低价",
    "一定赔",
    "一定补发",
    "十万公里没问题",
    "永不生锈",
)


def main() -> int:
    """Run I5 eval gate design check."""

    print("=" * 80)
    print("checking Phase 3-I-I real LLM eval gate design")

    errors: list[str] = []

    doc_result = check_doc(errors=errors)
    file_result = check_test_case_file()

    result = {
        "doc_result": doc_result,
        "test_case_file_result": file_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I real LLM eval gate design check failed")
        return 1

    print("Phase 3-I-I real LLM eval gate design check passed")
    return 0


def check_doc(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check eval gate design doc."""

    if not DOC_FILE.exists():
        errors.append(f"missing design doc: {DOC_FILE}")
        return {"doc_file": str(DOC_FILE), "exists": False}

    content = DOC_FILE.read_text(encoding="utf-8")

    missing_fragments = [
        fragment
        for fragment in REQUIRED_DOC_FRAGMENTS
        if fragment not in content
    ]
    missing_fields = [
        field
        for field in REQUIRED_OUTPUT_FIELDS
        if field not in content
    ]
    missing_forbidden = [
        fragment
        for fragment in FORBIDDEN_COMMITMENTS
        if fragment not in content
    ]

    if missing_fragments:
        errors.append(f"design doc missing fragments: {missing_fragments}")

    if missing_fields:
        errors.append(f"design doc missing output fields: {missing_fields}")

    if missing_forbidden:
        errors.append(
            f"design doc missing forbidden commitments: {missing_forbidden}"
        )

    return {
        "doc_file": str(DOC_FILE),
        "exists": True,
        "missing_fragments": missing_fragments,
        "missing_fields": missing_fields,
        "missing_forbidden": missing_forbidden,
    }


def check_test_case_file() -> dict[str, Any]:
    """Check whether test case file is present for I6."""

    return {
        "test_case_file": str(TEST_CASE_FILE),
        "exists": TEST_CASE_FILE.exists(),
        "note": (
            "I5 does not fail if the root-level test case file is absent. "
            "I6 can use the latest validated workbook path if needed."
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())