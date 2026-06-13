"""Check Phase 3-I-F unified KB routing design doc."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
DOC_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_unified_kb_routing_design_v0.1.md"
)

REQUIRED_FRAGMENTS: Final[tuple[str, ...]] = (
    "Phase 3-I-F Unified KB Routing Design v0.1",
    "quality_kb_v1",
    "logistics_kb_v1",
    "price_kb_v1",
    "spec_kb_v1",
    "LLM 不是事实来源",
    "RAG 不是承诺来源",
    "Spec",
    "Price",
    "Logistics",
    "Quality",
    "多意图冲突优先级",
    "高风险词强制策略",
    "retrieval_selected_module",
    "retrieval_source",
    "retrieval_collection_name",
    "retrieval_hit_count",
)

REQUIRED_FORBIDDEN_BOUNDARIES: Final[tuple[str, ...]] = (
    "万能适配",
    "最低价",
    "一定包邮",
    "永不生锈",
)


def main() -> int:
    """Run design doc check."""

    print("=" * 80)
    print("checking Phase 3-I-F routing design doc")

    errors: list[str] = []

    if not DOC_FILE.exists():
        errors.append(f"missing doc file: {DOC_FILE}")
        pprint({"errors": errors})
        return 1

    content = DOC_FILE.read_text(encoding="utf-8")

    for fragment in REQUIRED_FRAGMENTS:
        if fragment not in content:
            errors.append(f"missing required fragment: {fragment}")

    for fragment in REQUIRED_FORBIDDEN_BOUNDARIES:
        if fragment not in content:
            errors.append(f"missing boundary fragment: {fragment}")

    result = {
        "doc_file": str(DOC_FILE),
        "exists": DOC_FILE.exists(),
        "required_fragment_count": len(REQUIRED_FRAGMENTS),
        "boundary_fragment_count": len(REQUIRED_FORBIDDEN_BOUNDARIES),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-F routing design doc check failed")
        return 1

    print("Phase 3-I-F routing design doc check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())