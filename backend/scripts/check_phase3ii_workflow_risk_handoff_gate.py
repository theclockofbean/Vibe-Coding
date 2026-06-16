# ruff: noqa: E402,I001
"""Check Workflow applies Answer Strategy risk handoff gate."""

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


TARGET_CASES: Final[tuple[dict[str, Any], ...]] = (
    {
        "case_id": "RISK_SPEC_INSTALL_001",
        "query": "SKU003真皮那款有锥度要求吗 怎么安装",
        "expected_module": "spec",
    },
    {
        "case_id": "RISK_LOGISTICS_FEE_001",
        "query": "发顺丰去新疆多少差价",
        "expected_module": "logistics",
    },
    {
        "case_id": "RISK_PRICE_QUOTE_001",
        "query": "需要1000个SKU020 报个价",
        "expected_module": "price",
    },
    {
        "case_id": "RISK_QUALITY_CERT_001",
        "query": "你们有没有质检报告或者认证",
        "expected_module": "quality",
    },
    {
        "case_id": "RISK_ESCALATION_001",
        "query": "你们是骗子 东西根本用不了 我要差评投诉",
        "expected_module": None,
    },
    {
        "case_id": "RISK_CUSTOMIZATION_001",
        "query": "我想定制一批带我们公司LOGO的球头 500个",
        "expected_module": None,
    },
)

NORMAL_CASES: Final[tuple[dict[str, Any], ...]] = (
    {
        "case_id": "NORMAL_SPEC_001",
        "query": "SKU001螺纹规格是多少",
        "expected_module": "spec",
    },
)


def main() -> int:
    """Run workflow risk handoff gate regression."""

    print("=" * 80)
    print("checking Phase 3-I-I workflow risk handoff gate")

    configure_no_real_llm_mode()

    errors: list[str] = []
    results: list[dict[str, Any]] = []

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)

        for case in TARGET_CASES:
            result = evaluate_case(
                case=case,
                product_repository=product_repository,
                expect_handoff=True,
            )
            results.append(result)
            errors.extend(result["errors"])

        for case in NORMAL_CASES:
            result = evaluate_case(
                case=case,
                product_repository=product_repository,
                expect_handoff=False,
            )
            results.append(result)
            errors.extend(result["errors"])

    pprint(
        {
            "results": results,
            "errors": errors,
        }
    )

    if errors:
        print("Phase 3-I-I workflow risk handoff gate check failed")
        return 1

    print("Phase 3-I-I workflow risk handoff gate check passed")
    return 0


def configure_no_real_llm_mode() -> None:
    """Disable real LLM and real RAG path for targeted workflow check."""

    os.environ["LLM_ENABLE_REAL_API"] = "0"
    os.environ["LLM_OFFLINE_ENABLED"] = "0"
    os.environ["LLM_INTENT_ENABLED"] = "0"

    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "0"


def evaluate_case(
    *,
    case: dict[str, Any],
    product_repository: Any,
    expect_handoff: bool,
) -> dict[str, Any]:
    """Evaluate one workflow case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = case.get("expected_module")

    started_at = time.perf_counter()

    initial_state = create_initial_agent_state(
        session_id=f"{case_id.lower()}-session",
        channel="risk-handoff-regression",
        user_id="phase3ii-risk-handoff-regression",
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

    final_response = str(payload.get("final_response") or "")
    selected_module = payload.get("selected_module")
    needs_handoff = payload.get("needs_handoff")
    answer_handoff_required = payload.get("answer_handoff_required")
    answer_strategy_mode = payload.get("answer_strategy_mode")
    render_answer_strategy_handoff_required = metadata.get(
        "render_answer_strategy_handoff_required"
    )

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    errors: list[str] = []

    if expected_module is not None and selected_module != expected_module:
        errors.append(
            f"{case_id}: selected_module expected {expected_module}, got {selected_module}"
        )

    if expect_handoff:
        if answer_strategy_mode != "handoff_required":
            errors.append(
                f"{case_id}: answer_strategy_mode expected handoff_required, "
                f"got {answer_strategy_mode}"
            )

        if answer_handoff_required is not True:
            errors.append(
                f"{case_id}: answer_handoff_required expected True, "
                f"got {answer_handoff_required}"
            )

        if needs_handoff is not True:
            errors.append(
                f"{case_id}: needs_handoff expected True, got {needs_handoff}"
            )

        if render_answer_strategy_handoff_required is not True:
            errors.append(
                f"{case_id}: render_answer_strategy_handoff_required "
                f"expected True, got {render_answer_strategy_handoff_required}"
            )

        if not contains_handoff_text(final_response):
            errors.append(
                f"{case_id}: final_response missing handoff text"
            )
    else:
        if answer_strategy_mode == "handoff_required":
            errors.append(
                f"{case_id}: normal case should not be handoff_required"
            )

        if needs_handoff is True:
            errors.append(
                f"{case_id}: normal case should not set needs_handoff=True"
            )

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": selected_module,
        "answer_strategy_mode": answer_strategy_mode,
        "answer_handoff_required": answer_handoff_required,
        "needs_handoff": needs_handoff,
        "render_answer_strategy_handoff_required": (
            render_answer_strategy_handoff_required
        ),
        "latency_ms": latency_ms,
        "final_response_preview": final_response[:260],
        "errors": errors,
    }


def contains_handoff_text(
    text: str,
) -> bool:
    """Return whether text contains handoff wording."""

    return any(
        fragment in text
        for fragment in ("转人工", "人工确认", "人工客服", "人工处理")
    )


def as_dict(
    value: object,
) -> dict[str, Any]:
    """Return dict value or empty dict."""

    if isinstance(value, dict):
        return dict(value)

    return {}


if __name__ == "__main__":
    raise SystemExit(main())