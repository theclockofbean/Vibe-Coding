# ruff: noqa: E402,I001
"""Check LLMSafetyGuard behavior.

This script verifies LLM output cannot become a fact source or commitment
source.
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
from app.agent.llm.safety import LLMSafetyGuard
from app.agent.llm.schemas import (
    DEFAULT_FORBIDDEN_COMMITMENTS,
    LLMRequest,
    LLMResponse,
)


def check_safe_response_passes() -> bool:
    """Check safe response passes guard."""

    print("=" * 80)
    print("checking safe response")

    request = LLMRequest(
        task_type="summarize_evidence",
        user_text="SKU001 材质说明",
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
    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        guarded.is_safe is True,
        guarded.needs_handoff is False,
        guarded.metadata["final_response_allowed"] is False,
        guarded.metadata["fact_source_allowed"] is False,
        guarded.metadata["commitment_source_allowed"] is False,
    ]

    return all(checks)


def check_forbidden_commitment_blocked() -> bool:
    """Check exact forbidden commitments are blocked."""

    print("=" * 80)
    print("checking exact forbidden commitment")

    response = LLMResponse(
        request_id="guard-test-001",
        provider="local",
        model="manual-test",
        content="这个产品保证不生锈，而且一定包邮。",
    )

    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    guard_result = guarded.metadata["llm_safety_guard"]

    checks = [
        guarded.is_safe is False,
        guarded.needs_handoff is True,
        guarded.finish_reason == "safety_rejected",
        "forbidden_commitment" in guarded.safety_flags,
        "保证不生锈" in guard_result["forbidden_hits"],
        "一定包邮" in guard_result["forbidden_hits"],
        "[已移除高风险承诺]" in guarded.content,
    ]

    return all(checks)


def check_price_commitment_blocked() -> bool:
    """Check price commitment pattern is blocked."""

    print("=" * 80)
    print("checking price commitment")

    response = LLMResponse(
        request_id="guard-test-002",
        provider="local",
        model="manual-test",
        content="这款 99 元包邮，可以直接成交。",
    )

    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        guarded.is_safe is False,
        guarded.needs_handoff is True,
        "unauthorized_price_commitment" in guarded.safety_flags,
    ]

    return all(checks)


def check_logistics_commitment_blocked() -> bool:
    """Check logistics commitment pattern is blocked."""

    print("=" * 80)
    print("checking logistics commitment")

    response = LLMResponse(
        request_id="guard-test-003",
        provider="local",
        model="manual-test",
        content="今天一定发货，明天可以送达。",
    )

    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        guarded.is_safe is False,
        guarded.needs_handoff is True,
        "logistics_commitment" in guarded.safety_flags,
    ]

    return all(checks)


def check_quality_commitment_blocked() -> bool:
    """Check quality commitment pattern is blocked."""

    print("=" * 80)
    print("checking quality commitment")

    response = LLMResponse(
        request_id="guard-test-004",
        provider="local",
        model="manual-test",
        content="这个产品质量很好，放心用，完全没问题。",
    )

    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        guarded.is_safe is False,
        guarded.needs_handoff is True,
        "quality_commitment" in guarded.safety_flags,
    ]

    return all(checks)


def check_aftersale_commitment_blocked() -> bool:
    """Check aftersale commitment pattern is blocked."""

    print("=" * 80)
    print("checking aftersale commitment")

    response = LLMResponse(
        request_id="guard-test-005",
        provider="local",
        model="manual-test",
        content="售后一定能退，也可以直接补发。",
    )

    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        guarded.is_safe is False,
        guarded.needs_handoff is True,
        "aftersale_commitment" in guarded.safety_flags,
    ]

    return all(checks)


def check_client_marked_unsafe_preserved() -> bool:
    """Check unsafe client response remains unsafe."""

    print("=" * 80)
    print("checking client marked unsafe")

    request = LLMRequest(
        task_type="echo_test",
        user_text="这个产品保证不坏。",
    )
    response = EchoLLMClient().generate(request)
    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        response.is_safe is False,
        guarded.is_safe is False,
        guarded.needs_handoff is True,
        "client_marked_unsafe" in guarded.safety_flags,
    ]

    return all(checks)


def check_safe_outputs_contain_no_forbidden_fragments() -> bool:
    """Check safe guarded outputs contain no forbidden fragments."""

    print("=" * 80)
    print("checking safe outputs contain no forbidden fragments")

    request = LLMRequest(
        task_type="rewrite_safe_answer",
        user_text="SKU001 材质说明",
    )
    response = RuleBasedLLMClient().generate(request)
    guarded = LLMSafetyGuard().guard_response(response)

    pprint(guarded.to_dict())

    checks = [
        guarded.is_safe is True,
        all(
            fragment not in guarded.content
            for fragment in DEFAULT_FORBIDDEN_COMMITMENTS
        ),
    ]

    return all(checks)


def main() -> int:
    """Run LLMSafetyGuard checks."""

    results = [
        check_safe_response_passes(),
        check_forbidden_commitment_blocked(),
        check_price_commitment_blocked(),
        check_logistics_commitment_blocked(),
        check_quality_commitment_blocked(),
        check_aftersale_commitment_blocked(),
        check_client_marked_unsafe_preserved(),
        check_safe_outputs_contain_no_forbidden_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("llm safety guard check failed")
        return 1

    print("llm safety guard check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())