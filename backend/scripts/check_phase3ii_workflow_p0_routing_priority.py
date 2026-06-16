# ruff: noqa: E402,I001
"""Check Workflow P0 routing priority for Phase 3-I-I major gate."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import create_initial_agent_state
from app.agent.state import state_to_response_payload
from app.agent.workflow import run_agent_workflow
from app.core.database import get_session_factory
from app.repositories import ProductRepository


P0_EXPECTATIONS: Final[tuple[dict[str, str], ...]] = (
    {
        "case_id": "TC_SPEC_004",
        "query": "SKU004不锈钢子弹头 给我报一下全部参数",
        "expected": "spec",
    },
    {
        "case_id": "TC_SPEC_007",
        "query": "你们最长的杆是多少 哪款",
        "expected": "spec",
    },
    {
        "case_id": "TC_SPEC_011",
        "query": "你们钛合金材质的球头有哪些款",
        "expected": "spec",
    },
    {
        "case_id": "TC_LOGI_002",
        "query": "能发顺丰吗 我在浙江 要补多少钱",
        "expected": "logistics",
    },
    {
        "case_id": "TC_LOGI_003",
        "query": "发顺丰去新疆多少差价",
        "expected": "logistics",
    },
    {
        "case_id": "TC_PRICE_002",
        "query": "我要100个SKU006钛合金球头 批发价多少",
        "expected": "price",
    },
    {
        "case_id": "TC_PRICE_007",
        "query": "需要1000个SKU020 报个价",
        "expected": "price",
    },
    {
        "case_id": "TC_PRICE_008",
        "query": "我老客户了 给我个实在价",
        "expected": "price",
    },
    {
        "case_id": "TC_QUAL_001",
        "query": "你们的是原厂件吗",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_003",
        "query": "钛合金和铝合金球头哪个更好 有什么区别",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_004",
        "query": "SKU003真皮包覆的会不会掉色或者发霉",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_005",
        "query": "夜光球头用久了夜光会不会褪色",
        "expected": "quality",
    },
    {
        "case_id": "TC_QUAL_008",
        "query": "你们有没有质检报告或者认证",
        "expected": "quality",
    },
    {
        "case_id": "TC_ESCA_001",
        "query": "你们是骗子 东西根本用不了 我要差评投诉",
        "expected": "escalation",
    },
    {
        "case_id": "TC_ESCA_002",
        "query": "我想定制一批带我们公司LOGO的球头 500个",
        "expected": "escalation",
    },
    {
        "case_id": "TC_ESCA_003",
        "query": "我按照你说的装上去结果球头裂了 你们赔不赔",
        "expected": "escalation",
    },
)


def main() -> int:
    """Run Workflow P0 routing priority check."""

    print("=" * 80)
    print("checking Phase 3-I-I workflow P0 routing priority")

    configure_targeted_mode()

    errors: list[str] = []
    rows: list[dict[str, Any]] = []

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)

        for item in P0_EXPECTATIONS:
            row = evaluate_case(
                case_id=item["case_id"],
                query=item["query"],
                expected=item["expected"],
                product_repository=product_repository,
            )
            rows.append(row)
            errors.extend(row["errors"])

    result = {
        "rows": rows,
        "by_expected_actual": count_expected_actual(rows),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I workflow P0 routing priority check failed")
        return 1

    print("Phase 3-I-I workflow P0 routing priority check passed")
    return 0


def configure_targeted_mode() -> None:
    """Disable external calls for deterministic routing check."""

    os.environ["LLM_ENABLE_REAL_API"] = "0"
    os.environ["LLM_OFFLINE_ENABLED"] = "0"
    os.environ["LLM_INTENT_ENABLED"] = "0"

    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "0"


def evaluate_case(
    *,
    case_id: str,
    query: str,
    expected: str,
    product_repository: Any,
) -> dict[str, Any]:
    """Evaluate one workflow routing case."""

    started_at = time.perf_counter()

    initial_state = create_initial_agent_state(
        session_id=f"{case_id.lower()}-workflow-routing-priority",
        channel="phase3ii-workflow-routing-priority",
        user_id="phase3ii-workflow-routing-priority",
        user_text=query,
    )

    final_state = run_agent_workflow(
        initial_state=initial_state,
        product_repository=product_repository,
        conversation_repository=None,
        limit=5,
    )

    payload = state_to_response_payload(final_state)
    metadata = as_dict(payload.get("metadata"))

    selected_module = payload.get("selected_module")
    answer_strategy_mode = payload.get("answer_strategy_mode")
    answer_handoff_required = payload.get("answer_handoff_required")
    handoff_required = payload.get("handoff_required")
    final_response = str(payload.get("final_response") or "")
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    intent_metadata = extract_intent_metadata(payload=payload, metadata=metadata)

    effective_module = resolve_effective_module(
        expected=expected,
        selected_module=selected_module,
        handoff_required=handoff_required,
        answer_handoff_required=answer_handoff_required,
        intent_metadata=intent_metadata,
    )

    errors: list[str] = []

    if effective_module != expected:
        errors.append(
            f"{case_id}: expected {expected}, got {selected_module}; "
            f"effective={effective_module}"
        )

    return {
        "case_id": case_id,
        "query": query,
        "expected": expected,
        "selected_module": selected_module,
        "effective_module": effective_module,
        "answer_strategy_mode": answer_strategy_mode,
        "answer_handoff_required": answer_handoff_required,
        "handoff_required": handoff_required,
        "intent_metadata": intent_metadata,
        "latency_ms": latency_ms,
        "final_response_preview": final_response[:220],
        "errors": errors,
    }


def extract_intent_metadata(
    *,
    payload: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Extract likely intent-related metadata fields."""

    keys = (
        "intent",
        "classified_intent",
        "intent_confidence",
        "intent_reason",
        "llm_intent",
        "rule_based_intent",
        "phase3ii_priority_router",
        "matched_intent",
        "selected_module_source",
        "phase3ii_priority_intent",
        "phase3ii_priority_local_recheck_intent",
        "phase3ii_priority_intent_reapplied",
    )

    result: dict[str, Any] = {}

    for key in keys:
        if key in payload:
            result[f"payload.{key}"] = payload.get(key)
        if key in metadata:
            result[f"metadata.{key}"] = metadata.get(key)

    nested_candidates = (
        "intent_classification",
        "llm_intent_classification",
        "router",
        "routing",
        "module_routing",
    )

    for key in nested_candidates:
        if key in metadata:
            result[f"metadata.{key}"] = metadata.get(key)

    return result


def count_expected_actual(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Count expected -> effective module pairs."""

    counts: dict[str, int] = {}

    for row in rows:
        key = f"{row['expected']} -> {row.get('effective_module')}"
        counts[key] = counts.get(key, 0) + 1

    return counts


def resolve_effective_module(
    *,
    expected: str,
    selected_module: object,
    handoff_required: object,
    answer_handoff_required: object,
    intent_metadata: dict[str, Any],
) -> str | None:
    """Resolve evaluation module without treating escalation as RAG module."""

    selected = selected_module if isinstance(selected_module, str) else None

    if expected != "escalation":
        return selected

    metadata_values = {
        value
        for value in intent_metadata.values()
        if isinstance(value, str)
    }

    escalation_detected = (
        "escalation" in metadata_values
        or intent_metadata.get("metadata.phase3ii_priority_intent") == "escalation"
        or intent_metadata.get("metadata.phase3ii_priority_local_recheck_intent")
        == "escalation"
    )

    if selected == "general" and escalation_detected and (
        handoff_required is True or answer_handoff_required is True
    ):
        return "escalation"

    return selected


def as_dict(value: object) -> dict[str, Any]:
    """Return dict value or empty dict."""

    if isinstance(value, dict):
        return dict(value)

    return {}


if __name__ == "__main__":
    raise SystemExit(main())