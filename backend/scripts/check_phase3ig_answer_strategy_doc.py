"""Check Phase 3-I-G multi-module answer strategy design doc."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DOC_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.md"
)

REQUIRED_FRAGMENTS: Final[tuple[str, ...]] = (
    "Phase 3-I-G Multi-module Answer Strategy v0.1",
    "LLM 不是事实来源",
    "RAG 不是承诺来源",
    "single_primary",
    "primary_with_boundary_note",
    "split_required",
    "safety_blocked",
    "handoff_required",
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
)

REQUIRED_FORBIDDEN_EXAMPLES: Final[tuple[str, ...]] = (
    "包邮价",
    "适配后马上发",
    "高质量低价",
    "一定赔",
    "一定补发",
    "保证适配且质量没问题",
)


def main() -> int:
    """Run answer strategy doc check."""

    print("=" * 80)
    print("checking Phase 3-I-G answer strategy doc")

    errors: list[str] = []

    if not DOC_FILE.exists():
        errors.append(f"missing doc file: {DOC_FILE}")
        pprint({"errors": errors})
        return 1

    content = DOC_FILE.read_text(encoding="utf-8")

    for fragment in REQUIRED_FRAGMENTS:
        if fragment not in content:
            errors.append(f"missing required fragment: {fragment}")

    for fragment in REQUIRED_FORBIDDEN_EXAMPLES:
        if fragment not in content:
            errors.append(f"missing forbidden example: {fragment}")

    result = {
        "doc_file": str(DOC_FILE),
        "required_fragment_count": len(REQUIRED_FRAGMENTS),
        "forbidden_example_count": len(REQUIRED_FORBIDDEN_EXAMPLES),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-G answer strategy doc check failed")
        return 1

    print("Phase 3-I-G answer strategy doc check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())