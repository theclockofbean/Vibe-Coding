# ruff: noqa: E402,I001
"""Check LLMClient contract.

This script verifies offline LLM clients and schemas.

It does not call real LLM APIs, generate business commitments, write database
records, or modify workflow final_response.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.client import (
    EchoLLMClient,
    RuleBasedLLMClient,
)
from app.agent.llm.schemas import (
    DISALLOWED_LLM_TASK_TYPES,
    SUPPORTED_LLM_TASK_TYPES,
    LLMContractError,
    LLMRequest,
)


def check_request_response_contract() -> bool:
    """Check request and response serialization."""

    print("=" * 80)
    print("checking LLM request / response contract")

    request = LLMRequest(
        task_type="echo_test",
        user_text="SKU001 材质说明",
        structured_facts={
            "sku_id": "SKU001",
            "material": "铝合金6061",
        },
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "content": "铝合金 6061 的一般说明。",
            }
        ],
    )

    response = EchoLLMClient().generate(request)

    pprint(request.to_dict())
    pprint(response.to_dict())

    checks = [
        request.task_type in SUPPORTED_LLM_TASK_TYPES,
        response.request_id == request.request_id,
        response.provider == "local",
        response.model == "echo-llm-v1",
        response.is_safe is True,
        response.needs_handoff is False,
        response.metadata["final_response_allowed"] is False,
    ]

    return all(checks)


def check_rule_based_client_contract() -> bool:
    """Check RuleBasedLLMClient contract."""

    print("=" * 80)
    print("checking RuleBasedLLMClient contract")

    request = LLMRequest(
        task_type="summarize_evidence",
        user_text="SKU001 质量说明",
        structured_facts={
            "sku_id": "SKU001",
        },
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "content": "仅作一般说明。",
            }
        ],
    )

    response = RuleBasedLLMClient().generate(request)

    pprint(response.to_dict())

    checks = [
        response.request_id == request.request_id,
        response.provider == "local",
        response.model == "rule-based-llm-v1",
        response.is_safe is True,
        response.needs_handoff is False,
        response.metadata["fact_source_allowed"] is False,
        response.metadata["commitment_source_allowed"] is False,
    ]

    return all(checks)


def check_disallowed_task_types() -> bool:
    """Check disallowed task types are rejected."""

    print("=" * 80)
    print("checking disallowed task types")

    rejected: list[str] = []

    for task_type in DISALLOWED_LLM_TASK_TYPES:
        try:
            LLMRequest(
                task_type=task_type,
                user_text="test",
            )
        except LLMContractError:
            rejected.append(task_type)

    pprint(
        {
            "disallowed_task_types": sorted(DISALLOWED_LLM_TASK_TYPES),
            "rejected": sorted(rejected),
        }
    )

    return set(rejected) == DISALLOWED_LLM_TASK_TYPES


def check_invalid_task_type() -> bool:
    """Check invalid task type is rejected."""

    print("=" * 80)
    print("checking invalid task type")

    try:
        LLMRequest(
            task_type="unknown_task",
            user_text="test",
        )
    except LLMContractError as exc:
        print(str(exc))
        return True

    return False


def main() -> int:
    """Run LLM contract checks."""

    results = [
        check_request_response_contract(),
        check_rule_based_client_contract(),
        check_disallowed_task_types(),
        check_invalid_task_type(),
    ]

    print("=" * 80)

    if not all(results):
        print("llm client contract check failed")
        return 1

    print("llm client contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())