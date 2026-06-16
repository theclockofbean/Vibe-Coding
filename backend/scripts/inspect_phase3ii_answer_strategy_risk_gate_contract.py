"""Inspect Answer Strategy risk gate contract for Phase 3-I-I."""

from __future__ import annotations

import json
import re
from pathlib import Path
from pprint import pprint
from typing import Any, Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

ANSWER_STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"
REPORT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs/evaluation/phase3ii_real_llm_50_case_eval_report.json"
)

REQUIRED_ANCHORS: Final[tuple[str, ...]] = (
    "class AnswerStrategyDecision",
    "def decide_answer_strategy",
    "safety_blocked",
    "handoff_required",
    "answer_strategy_mode",
    "primary_with_boundary_note",
    "split_required",
)

RISK_MARKERS: Final[tuple[str, ...]] = (
    "forbidden",
    "risk",
    "handoff",
    "safety",
    "commitment",
    "boundary",
    "price",
    "logistics",
    "quality",
    "spec",
)

RISK_REASON_MARKERS: Final[tuple[str, ...]] = (
    "expected handoff was not triggered",
    "risk case was not gated",
)


def main() -> int:
    """Inspect answer strategy risk gate contract."""

    print("=" * 80)
    print("inspecting Phase 3-I-I answer strategy risk gate contract")

    errors: list[str] = []

    answer_strategy_result = inspect_answer_strategy_file(errors=errors)
    workflow_result = inspect_workflow_gate_usage(errors=errors)
    report_result = inspect_latest_risk_failures(errors=errors)

    result = {
        "answer_strategy_result": answer_strategy_result,
        "workflow_result": workflow_result,
        "report_result": report_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I answer strategy risk gate contract inspection failed")
        return 1

    print("Phase 3-I-I answer strategy risk gate contract inspection passed")
    return 0


def inspect_answer_strategy_file(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect answer strategy source."""

    if not ANSWER_STRATEGY_FILE.exists():
        errors.append(f"missing answer strategy file: {ANSWER_STRATEGY_FILE}")
        return {"exists": False, "path": str(ANSWER_STRATEGY_FILE)}

    content = ANSWER_STRATEGY_FILE.read_text(encoding="utf-8")
    missing_anchors = [
        anchor
        for anchor in REQUIRED_ANCHORS
        if anchor not in content
    ]

    if missing_anchors:
        errors.append(f"answer strategy missing anchors: {missing_anchors}")

    return {
        "exists": True,
        "path": str(ANSWER_STRATEGY_FILE.relative_to(BACKEND_ROOT)),
        "missing_anchors": missing_anchors,
        "decision_fields": extract_dataclass_fields(content=content),
        "functions": extract_function_names(content=content),
        "risk_related_lines": extract_lines(
            content=content,
            markers=RISK_MARKERS,
            limit=120,
        ),
        "recommended_patch_anchors": find_recommended_patch_anchors(content=content),
    }


def inspect_workflow_gate_usage(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect workflow usage of answer strategy."""

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        return {"exists": False, "path": str(WORKFLOW_FILE)}

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    return {
        "exists": True,
        "path": str(WORKFLOW_FILE.relative_to(BACKEND_ROOT)),
        "answer_strategy_lines": extract_lines(
            content=content,
            markers=(
                "decide_answer_strategy",
                "answer_strategy",
                "_apply_answer_strategy_metadata",
                "_apply_answer_strategy_render_gate",
                "render_safety_blocked",
                "needs_handoff",
            ),
            limit=120,
        ),
    }


def inspect_latest_risk_failures(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect latest risk gate failures from JSON report."""

    if not REPORT_FILE.exists():
        errors.append(f"missing evaluation report: {REPORT_FILE}")
        return {"exists": False, "path": str(REPORT_FILE)}

    data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = data["results"]

    failures = [
        item
        for item in results
        if has_risk_gate_failure(item)
    ]

    return {
        "exists": True,
        "path": str(REPORT_FILE),
        "risk_gate_failure_count": len(failures),
        "compact_failures": [
            {
                "case_id": item.get("case_id"),
                "query": item.get("query"),
                "category": item.get("category"),
                "scenario_type": item.get("scenario_type"),
                "expected_module": item.get("expected_module"),
                "selected_module": item.get("selected_module"),
                "answer_strategy_mode": item.get("answer_strategy_mode"),
                "failure_reasons": item.get("failure_reasons", [])[:4],
            }
            for item in failures
        ],
        "recommended_risk_keyword_groups": build_recommended_keyword_groups(),
    }


def has_risk_gate_failure(
    item: dict[str, Any],
) -> bool:
    """Return whether one result has risk gate failure."""

    reasons = [str(reason) for reason in item.get("failure_reasons", [])]

    return any(
        marker in reason
        for marker in RISK_REASON_MARKERS
        for reason in reasons
    )


def extract_dataclass_fields(
    *,
    content: str,
) -> list[str]:
    """Extract likely dataclass fields from AnswerStrategyDecision."""

    match = re.search(
        r"class AnswerStrategyDecision.*?(?=\n\nclass|\n\ndef|\Z)",
        content,
        flags=re.DOTALL,
    )

    if not match:
        return []

    block = match.group(0)
    fields: list[str] = []

    for line in block.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        field_match = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*:", stripped)

        if field_match:
            fields.append(field_match.group(1))

    return fields


def extract_function_names(
    *,
    content: str,
) -> list[str]:
    """Extract function names."""

    return re.findall(r"^def ([a-zA-Z_][a-zA-Z0-9_]*)\(", content, flags=re.MULTILINE)


def extract_lines(
    *,
    content: str,
    markers: tuple[str, ...],
    limit: int,
) -> list[str]:
    """Extract source lines containing markers."""

    lines: list[str] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        lowered = line.lower()

        if any(marker.lower() in lowered for marker in markers):
            lines.append(f"{line_number}: {line.rstrip()}")

    return lines[:limit]


def find_recommended_patch_anchors(
    *,
    content: str,
) -> dict[str, bool]:
    """Find likely safe patch anchors."""

    anchors = {
        "has_decide_answer_strategy": "def decide_answer_strategy" in content,
        "has_return_decision": "return AnswerStrategyDecision" in content,
        "has_candidate_modules": "candidate_modules" in content,
        "has_risk_tags": "risk_tags" in content,
        "has_boundary_notes": "boundary_notes" in content,
        "has_safety_blocked_mode": "safety_blocked" in content,
        "has_handoff_required": "handoff_required" in content,
    }

    return anchors


def build_recommended_keyword_groups() -> dict[str, tuple[str, ...]]:
    """Return recommended keyword groups for the next patch."""

    return {
        "fitment_or_installation": (
            "适配",
            "车型",
            "宝马",
            "安装",
            "怎么装",
            "装不上",
            "锥度要求",
        ),
        "price_or_discount": (
            "报价",
            "报个价",
            "批发",
            "优惠",
            "便宜",
            "实在价",
            "老客户",
            "最低",
        ),
        "logistics_exception_or_fee": (
            "运费",
            "补差",
            "差价",
            "破损",
            "压变形",
            "退换货",
            "换货",
            "退货",
            "澳门",
            "港澳台",
            "新疆",
            "顺丰",
        ),
        "quality_claim_or_certification": (
            "原厂",
            "OEM正品",
            "质检",
            "认证",
            "检测报告",
            "寿命",
            "耐用",
            "发霉",
            "开裂",
            "褪色",
        ),
        "complaint_or_escalation": (
            "投诉",
            "差评",
            "骗子",
            "客服",
            "人工",
            "售后",
            "赔",
            "退款",
            "定制",
            "LOGO",
            "方案",
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())