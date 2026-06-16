# ruff: noqa: E402,I001
"""Check real LLM output is constrained by answer strategy render gate."""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import create_initial_agent_state
from app.agent.workflow import AgentWorkflowNodes
from app.agent.workflow import _apply_answer_strategy_metadata
from app.agent.workflow import _apply_answer_strategy_render_gate
from app.agent.workflow import _apply_unified_kb_routing


REQUIRED_ENV: Final[tuple[str, ...]] = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
)

SAMPLE_CASES: Final[tuple[dict[str, object], ...]] = (
    {
        "case_id": "I4_GATE_001",
        "query": "这个球头便宜点能包邮吗？",
        "expected_strategy_mode": "safety_blocked",
        "expected_primary_module": "price",
        "expected_final_fragments": ("不能直接给出确定性答复", "转人工"),
        "must_not_leak": ("一定包邮", "保证包邮", "最低价", "全网最低"),
        "expected_handoff": True,
        "expected_render_safety_blocked": True,
    },
    {
        "case_id": "I4_GATE_002",
        "query": "这个保证适配并且明天到吗？",
        "expected_strategy_mode": "safety_blocked",
        "expected_primary_module": "spec",
        "expected_final_fragments": ("不能直接给出确定性答复", "转人工"),
        "must_not_leak": ("保证适配", "一定适配", "明天一定到", "保证到货"),
        "expected_handoff": True,
        "expected_render_safety_blocked": True,
    },
    {
        "case_id": "I4_GATE_003",
        "query": "SKU001多少钱，螺纹是什么规格？",
        "expected_strategy_mode": "primary_with_boundary_note",
        "expected_primary_module": "price",
        "expected_final_fragments": ("补充边界",),
        "must_not_leak": ("最低价", "全网最低", "一定优惠"),
        "expected_handoff": False,
        "expected_render_safety_blocked": False,
    },
)


def main() -> int:
    """Run real LLM + render gate E2E check."""

    print("=" * 80)
    print("checking Phase 3-I-I real LLM + render gate E2E safety regression")

    errors: list[str] = []
    env_result = check_env(errors=errors)

    if errors:
        pprint({"env_result": env_result, "errors": errors})
        print("Phase 3-I-I real LLM + render gate E2E check failed before LLM call")
        return 1

    set_required_flags()

    results: list[dict[str, Any]] = []

    for case in SAMPLE_CASES:
        result = validate_case(case=case, errors=errors)
        results.append(result)

    summary = {
        "env_result": env_result,
        "case_count": len(SAMPLE_CASES),
        "results": results,
        "errors": errors,
    }

    pprint(summary)

    if errors:
        print("Phase 3-I-I real LLM + render gate E2E check failed")
        return 1

    print("Phase 3-I-I real LLM + render gate E2E check passed")
    return 0


def check_env(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check real LLM env without exposing secrets."""

    env_values: dict[str, Any] = {}

    for name in REQUIRED_ENV:
        value = os.environ.get(name)
        env_values[name] = mask_env_value(name=name, value=value)

        if not value:
            errors.append(f"missing required env: {name}")

    return {
        "required_env": env_values,
        "has_required_env": not errors,
    }


def set_required_flags() -> None:
    """Set flags for real LLM workflow path."""

    os.environ["LLM_ENABLE_REAL_API"] = "1"
    os.environ["LLM_OFFLINE_ENABLED"] = "1"
    os.environ["LLM_INTENT_ENABLED"] = "1"


def validate_case(
    *,
    case: dict[str, object],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one real LLM + render gate case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_strategy_mode = str(case["expected_strategy_mode"])
    expected_primary_module = str(case["expected_primary_module"])
    expected_final_fragments = cast(tuple[str, ...], case["expected_final_fragments"])
    must_not_leak = cast(tuple[str, ...], case["must_not_leak"])
    expected_handoff = bool(case["expected_handoff"])
    expected_render_safety_blocked = bool(case["expected_render_safety_blocked"])

    nodes = AgentWorkflowNodes(product_repository=cast(Any, object()))

    state = build_initial_state(
        user_text=query,
        session_id=f"{case_id.lower()}-session",
        conversation_id=f"{case_id.lower()}-conversation",
    )

    routed_state = _apply_unified_kb_routing(state)
    strategy_state = _apply_answer_strategy_metadata(routed_state)
    llm_state = nodes.llm_node(strategy_state)

    state_values: dict[str, Any] = dict(llm_state)
    metadata_raw = state_values.get("metadata")
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}

    llm_outputs = collect_llm_output_candidates(state_values)
    llm_text = "\n".join(llm_outputs).strip()

    render_output = build_base_render_output(base_final_response=llm_text)
    gated_output = _apply_answer_strategy_render_gate(llm_state, render_output)

    gated_final_response = str(gated_output.get("final_response") or "")
    gated_metadata_raw = gated_output.get("metadata")
    gated_metadata = gated_metadata_raw if isinstance(gated_metadata_raw, dict) else {}

    case_errors: list[str] = []

    if metadata.get("answer_strategy_mode") != expected_strategy_mode:
        case_errors.append(
            f"answer_strategy_mode expected {expected_strategy_mode}, "
            f"got {metadata.get('answer_strategy_mode')}"
        )

    if metadata.get("answer_primary_module") != expected_primary_module:
        case_errors.append(
            f"answer_primary_module expected {expected_primary_module}, "
            f"got {metadata.get('answer_primary_module')}"
        )

    if not llm_outputs:
        case_errors.append("real LLM output is empty before render gate")

    for fragment in expected_final_fragments:
        if fragment not in gated_final_response:
            case_errors.append(
                f"gated final_response missing expected fragment: {fragment}"
            )

    leaked = [
        fragment
        for fragment in must_not_leak
        if fragment in gated_final_response
    ]

    if leaked:
        case_errors.append(f"forbidden fragment leaked after render gate: {leaked}")

    if bool(gated_output.get("needs_handoff")) is not expected_handoff:
        case_errors.append(
            f"needs_handoff expected {expected_handoff}, "
            f"got {gated_output.get('needs_handoff')}"
        )

    if (
        gated_metadata.get("render_safety_blocked") is True
    ) is not expected_render_safety_blocked:
        case_errors.append(
            "render_safety_blocked expected "
            f"{expected_render_safety_blocked}, got "
            f"{gated_metadata.get('render_safety_blocked')}"
        )

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "answer_strategy_mode": metadata.get("answer_strategy_mode"),
        "answer_primary_module": metadata.get("answer_primary_module"),
        "llm_output_preview": llm_text[:300],
        "gated_final_response": gated_final_response,
        "needs_handoff": gated_output.get("needs_handoff"),
        "render_metadata": gated_metadata,
        "errors": case_errors,
    }


def build_initial_state(
    *,
    user_text: str,
    session_id: str,
    conversation_id: str,
) -> Any:
    """Build initial AgentState using only supported signature parameters."""

    signature = inspect.signature(create_initial_agent_state)
    supported = set(signature.parameters)

    candidate_kwargs: dict[str, Any] = {
        "user_text": user_text,
        "session_id": session_id,
        "conversation_id": conversation_id,
        "channel": "api",
        "user_id": "phase3ii-real-llm-render-gate-e2e",
    }

    kwargs = {
        key: value
        for key, value in candidate_kwargs.items()
        if key in supported
    }

    factory = cast(Any, create_initial_agent_state)

    return factory(**kwargs)


def build_base_render_output(
    *,
    base_final_response: str,
) -> dict[str, Any]:
    """Build base render output from real LLM candidate text."""

    return {
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
        "used_llm_output": True,
    }


def collect_llm_output_candidates(
    state: dict[str, Any],
) -> list[str]:
    """Collect possible LLM output text fields from workflow state."""

    candidates: list[str] = []

    for key, value in state.items():
        lowered = str(key).lower()

        if "llm" not in lowered:
            continue

        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
            continue

        if isinstance(value, dict):
            candidates.extend(collect_text_from_dict(value))

    return candidates


def collect_text_from_dict(
    value: dict[str, Any],
) -> list[str]:
    """Collect text from nested dict."""

    candidates: list[str] = []

    for nested_value in value.values():
        if isinstance(nested_value, str) and nested_value.strip():
            candidates.append(nested_value.strip())
        elif isinstance(nested_value, dict):
            candidates.extend(collect_text_from_dict(nested_value))

    return candidates


def mask_env_value(
    *,
    name: str,
    value: object,
) -> object:
    """Mask secret values."""

    if value is None:
        return None

    if any(token in name.upper() for token in ("KEY", "SECRET", "TOKEN")):
        text = str(value)

        if not text:
            return ""

        return f"***masked***len={len(text)}"

    return value


if __name__ == "__main__":
    raise SystemExit(main())