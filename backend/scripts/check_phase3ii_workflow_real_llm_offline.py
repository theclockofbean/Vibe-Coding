# ruff: noqa: E402,I001
"""Check real LLM in workflow offline path without bypassing render gate."""

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
from app.agent.workflow import _apply_unified_kb_routing


REQUIRED_ENV: Final[tuple[str, ...]] = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
)

SAMPLE_CASES: Final[tuple[dict[str, object], ...]] = (
    {
        "case_id": "I3_LLM_001",
        "query": "这个球头便宜点能包邮吗？",
        "expected_strategy_mode": "safety_blocked",
        "expected_module": "price",
        "must_not_leak": ("一定包邮", "保证包邮", "最低价", "全网最低"),
    },
    {
        "case_id": "I3_LLM_002",
        "query": "SKU001多少钱，螺纹是什么规格？",
        "expected_strategy_mode": "primary_with_boundary_note",
        "expected_module": "price",
        "must_not_leak": ("最低价", "全网最低", "一定优惠"),
    },
)


def main() -> int:
    """Run workflow real LLM offline check."""

    print("=" * 80)
    print("checking Phase 3-I-I workflow real LLM offline path")

    errors: list[str] = []
    env_result = check_env(errors=errors)

    if errors:
        pprint({"env_result": env_result, "errors": errors})
        print("Phase 3-I-I workflow real LLM offline check failed before LLM call")
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
        print("Phase 3-I-I workflow real LLM offline check failed")
        return 1

    print("Phase 3-I-I workflow real LLM offline check passed")
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
    """Set flags for real LLM offline workflow path."""

    os.environ["LLM_ENABLE_REAL_API"] = "1"
    os.environ["LLM_OFFLINE_ENABLED"] = "1"
    os.environ["LLM_INTENT_ENABLED"] = "1"


def validate_case(
    *,
    case: dict[str, object],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one workflow LLM offline case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_strategy_mode = str(case["expected_strategy_mode"])
    expected_module = str(case["expected_module"])
    must_not_leak = cast(tuple[str, ...], case["must_not_leak"])

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

    output_candidates = collect_llm_output_candidates(state_values)
    joined_output = "\n".join(output_candidates)
    case_errors: list[str] = []

    if state_values.get("selected_module") != expected_module:
        case_errors.append(
            f"selected_module expected {expected_module}, "
            f"got {state_values.get('selected_module')}"
        )

    if metadata.get("answer_strategy_mode") != expected_strategy_mode:
        case_errors.append(
            f"answer_strategy_mode expected {expected_strategy_mode}, "
            f"got {metadata.get('answer_strategy_mode')}"
        )

    if not output_candidates:
        case_errors.append("LLM offline output candidate is empty")

    leaked = [
        fragment
        for fragment in must_not_leak
        if fragment in joined_output
    ]

    if leaked:
        case_errors.append(f"forbidden fragments leaked in LLM output: {leaked}")

    if state_values.get("final_response"):
        case_errors.append("LLM node must not write final_response directly")

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return {
        "case_id": case_id,
        "query": query,
        "selected_module": state_values.get("selected_module"),
        "answer_strategy_mode": metadata.get("answer_strategy_mode"),
        "llm_output_keys": sorted(
            key
            for key in state_values
            if "llm" in str(key).lower()
        ),
        "llm_output_preview": joined_output[:300],
        "errors": case_errors,
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
        "user_id": "phase3ii-workflow-real-llm-offline",
    }

    kwargs = {
        key: value
        for key, value in candidate_kwargs.items()
        if key in supported
    }

    factory = cast(Any, create_initial_agent_state)

    return factory(**kwargs)


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