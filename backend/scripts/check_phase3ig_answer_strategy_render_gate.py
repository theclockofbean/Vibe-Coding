# ruff: noqa: E402,I001
"""Check Phase 3-I-G answer strategy render gate."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.workflow import _apply_answer_strategy_metadata
from app.agent.workflow import _apply_answer_strategy_render_gate
from app.agent.workflow import _apply_unified_kb_routing


SAMPLE_CASES: Final[tuple[dict[str, object], ...]] = (
    {
        "case_id": "GATE_RENDER_001",
        "query": "SKU001多少钱，螺纹是什么规格？",
        "base_final_response": "这类问题涉及报价，需要人工确认。",
        "expected_mode": "primary_with_boundary_note",
        "expected_contains": ["这类问题涉及报价", "补充边界"],
        "expected_handoff": False,
        "expected_safety_blocked": False,
    },
    {
        "case_id": "GATE_RENDER_002",
        "query": "便宜点能包邮吗？",
        "base_final_response": "可以给你优惠并包邮。",
        "expected_mode": "safety_blocked",
        "expected_contains": ["不能直接给出确定性答复", "转人工"],
        "expected_handoff": True,
        "expected_safety_blocked": True,
    },
    {
        "case_id": "GATE_RENDER_003",
        "query": "这个保证适配并且明天到吗？",
        "base_final_response": "保证适配并且明天到。",
        "expected_mode": "safety_blocked",
        "expected_contains": ["不能直接给出确定性答复", "转人工"],
        "expected_handoff": True,
        "expected_safety_blocked": True,
    },
)

FORBIDDEN_OUTPUT_FRAGMENTS: Final[tuple[str, ...]] = (
    "可以给你优惠并包邮",
    "保证适配并且明天到",
)


def main() -> int:
    """Run answer strategy render gate check."""

    print("=" * 80)
    print("checking Phase 3-I-G answer strategy render gate")

    errors: list[str] = []
    results: list[dict[str, Any]] = []

    for case in SAMPLE_CASES:
        result = validate_case(case=case, errors=errors)
        results.append(result)

    summary = {
        "case_count": len(SAMPLE_CASES),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }

    pprint(summary)

    if errors:
        print("Phase 3-I-G answer strategy render gate check failed")
        return 1

    print("Phase 3-I-G answer strategy render gate check passed")
    return 0


def validate_case(
    *,
    case: dict[str, object],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one render gate sample."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    base_final_response = str(case["base_final_response"])
    expected_mode = str(case["expected_mode"])
    expected_contains = cast(list[str], case["expected_contains"])
    expected_handoff = bool(case["expected_handoff"])
    expected_safety_blocked = bool(case["expected_safety_blocked"])

    state: dict[str, Any] = {
        "user_text": query,
        "current_message": query,
        "query": query,
        "metadata": {},
        "retrieved_chunks": [],
    }

    routed_state = _apply_unified_kb_routing(cast(Any, state))
    strategy_state = cast(
        dict[str, Any],
        _apply_answer_strategy_metadata(routed_state),
    )
    metadata = cast(dict[str, Any], strategy_state.get("metadata") or {})

    render_output: dict[str, Any] = {
        "final_response": base_final_response,
        "response_sources": [],
        "response_warnings": [],
        "risk_flags": [],
        "risk_reasons": [],
        "metadata": {
            "render_mode": "grounded",
            "render_safety_blocked": False,
        },
        "needs_handoff": False,
        "is_grounded": True,
        "used_llm_output": False,
    }

    gated_output = _apply_answer_strategy_render_gate(
        cast(Any, strategy_state),
        render_output,
    )
    final_response = str(gated_output.get("final_response", ""))
    render_metadata = cast(dict[str, Any], gated_output.get("metadata") or {})
    case_errors: list[str] = []

    if metadata.get("answer_strategy_mode") != expected_mode:
        case_errors.append(
            f"answer_strategy_mode expected {expected_mode}, "
            f"got {metadata.get('answer_strategy_mode')}"
        )

    for fragment in expected_contains:
        if fragment not in final_response:
            case_errors.append(f"missing expected final_response fragment: {fragment}")

    for fragment in FORBIDDEN_OUTPUT_FRAGMENTS:
        if expected_safety_blocked and fragment in final_response:
            case_errors.append(f"forbidden fragment leaked: {fragment}")

    if bool(gated_output.get("needs_handoff")) is not expected_handoff:
        case_errors.append(
            f"needs_handoff expected {expected_handoff}, "
            f"got {gated_output.get('needs_handoff')}"
        )

    if (
        render_metadata.get("render_safety_blocked") is True
    ) is not expected_safety_blocked:
        case_errors.append(
            "render_safety_blocked expected "
            f"{expected_safety_blocked}, got "
            f"{render_metadata.get('render_safety_blocked')}"
        )

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "answer_strategy_mode": metadata.get("answer_strategy_mode"),
        "final_response": final_response,
        "needs_handoff": gated_output.get("needs_handoff"),
        "render_metadata": render_metadata,
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())