# ruff: noqa: E402,I001
"""Targeted workflow regression after parser SKU boundary fixes.

This check does not call real LLM. It verifies that SKU-adjacent Chinese
queries no longer fail with "no SKU ID".
"""

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


TARGET_CASES: Final[tuple[dict[str, object], ...]] = (
    {
        "case_id": "TC_SPEC_001_TARGET",
        "query": "SKU001铝合金竞技换挡球头的螺纹规格是多少",
        "expected_module": "spec",
        "must_contain_any": ("SKU001", "M8×1.25", "M8"),
        "must_not_contain": (
            "no SKU ID, OEM reference number, or thread spec was found",
            "当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
        ),
    },
    {
        "case_id": "TC_SPEC_002_TARGET",
        "query": "SKU002碳纤维的杆长是多少毫米",
        "expected_module": "spec",
        "must_contain_any": ("SKU002", "40mm", "40"),
        "must_not_contain": (
            "no SKU ID, OEM reference number, or thread spec was found",
            "当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
        ),
    },
    {
        "case_id": "TC_SPEC_003_TARGET",
        "query": "SKU003真皮那款有锥度要求吗 怎么安装",
        "expected_module": "spec",
        "must_contain_any": ("SKU003", "1:10", "锥度"),
        "must_not_contain": (
            "no SKU ID, OEM reference number, or thread spec was found",
            "当前只支持按 SKU、OEM 对照号或螺纹规格查询产品规格",
        ),
    },
    {
        "case_id": "TC_PRICE_SKU_TARGET",
        "query": "SKU032价格368元 能便宜点吗",
        "expected_module": "price",
        "must_contain_any": ("SKU032", "报价", "人工", "价格"),
        "must_not_contain": (
            "no SKU ID, OEM reference number, or thread spec was found",
        ),
    },
    {
        "case_id": "TC_QUAL_SKU_TARGET",
        "query": "SKU004会不会生锈",
        "expected_module": "quality",
        "must_contain_any": ("SKU004", "304不锈钢", "生锈", "耐腐蚀"),
        "must_not_contain": (
            "no SKU ID, OEM reference number, or thread spec was found",
        ),
    },
)


def main() -> int:
    """Run targeted parser workflow regression."""

    print("=" * 80)
    print("checking Phase 3-I-I targeted parser workflow regression")

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
            )
            results.append(result)

            if result["errors"]:
                errors.extend(
                    f"{result['case_id']}: {error}"
                    for error in result["errors"]
                )

    pprint(
        {
            "case_count": len(TARGET_CASES),
            "results": results,
            "errors": errors,
        }
    )

    if errors:
        print("Phase 3-I-I targeted parser workflow regression failed")
        return 1

    print("Phase 3-I-I targeted parser workflow regression passed")
    return 0


def as_tuple(
    value: object,
) -> tuple[str, ...]:
    """Convert tuple/list/scalar value to tuple[str, ...]."""

    if value is None:
        return ()

    if isinstance(value, tuple):
        return tuple(str(item) for item in value)

    if isinstance(value, list):
        return tuple(str(item) for item in value)

    return (str(value),)


def configure_no_real_llm_mode() -> None:
    """Disable real LLM path for targeted parser regression."""

    os.environ["LLM_ENABLE_REAL_API"] = "0"
    os.environ["LLM_OFFLINE_ENABLED"] = "0"
    os.environ["LLM_INTENT_ENABLED"] = "0"

    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "0"
    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "0"


def evaluate_case(
    *,
    case: dict[str, object],
    product_repository: Any,
) -> dict[str, Any]:
    """Evaluate one targeted workflow case."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = str(case["expected_module"])
    must_contain_any = as_tuple(case.get("must_contain_any"))
    must_not_contain = as_tuple(case.get("must_not_contain"))

    started_at = time.perf_counter()
    errors: list[str] = []

    initial_state = create_initial_agent_state(
        session_id=f"{case_id.lower()}-session",
        channel="parser-regression",
        user_id="phase3ii-targeted-parser-regression",
        user_text=query,
    )

    final_state = run_agent_workflow(
        initial_state=initial_state,
        product_repository=product_repository,
        conversation_repository=None,
        limit=5,
    )

    payload = state_to_response_payload(final_state)
    final_response = str(payload.get("final_response") or "")
    selected_module = payload.get("selected_module")
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    if selected_module != expected_module:
        errors.append(
            f"selected_module expected {expected_module}, got {selected_module}"
        )

    if not final_response:
        errors.append("final_response is empty")

    if must_contain_any and not any(
        fragment in final_response
        for fragment in must_contain_any
    ):
        errors.append(f"missing any expected fragment: {must_contain_any}")

    leaked = [
        fragment
        for fragment in must_not_contain
        if fragment in final_response
    ]

    if leaked:
        errors.append(f"unexpected parser failure fragment leaked: {leaked}")

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": selected_module,
        "latency_ms": latency_ms,
        "final_response_preview": final_response[:300],
        "errors": errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())