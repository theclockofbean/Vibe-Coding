# ruff: noqa: E402,I001
"""Check RuleBasedLLMClient behavior.

This script verifies the offline rule-based LLM client does not become a fact
or commitment source.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm import (
    DEFAULT_FORBIDDEN_COMMITMENTS,
    LLMRequest,
    RuleBasedLLMClient,
)


def check_safe_evidence_summary() -> bool:
    """Check safe summarize_evidence task."""

    print("=" * 80)
    print("checking safe evidence summary")

    request = LLMRequest(
        task_type="summarize_evidence",
        user_text="SKU001 材质说明",
        structured_facts={
            "sku_id": "SKU001",
            "material": "铝合金6061",
        },
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "content": "铝合金 6061 常用于轻量化零件。",
            }
        ],
    )

    response = RuleBasedLLMClient().generate(request)

    pprint(response.to_dict())

    checks = [
        response.is_safe is True,
        response.needs_handoff is False,
        response.error is None,
        "仅可用于非承诺性说明" in response.content,
        response.metadata["final_response_allowed"] is False,
    ]

    return all(checks)


def check_insufficient_evidence() -> bool:
    """Check insufficient evidence behavior."""

    print("=" * 80)
    print("checking insufficient evidence")

    request = LLMRequest(
        task_type="summarize_evidence",
        user_text="SKU001 是否一定不会掉漆",
    )

    response = RuleBasedLLMClient().generate(request)

    pprint(response.to_dict())

    checks = [
        response.is_safe is True,
        response.needs_handoff is False,
        "证据不足" in response.content,
        response.metadata["fact_source_allowed"] is False,
    ]

    return all(checks)


def check_forbidden_commitment_rejection() -> bool:
    """Check forbidden commitments trigger rejection."""

    print("=" * 80)
    print("checking forbidden commitment rejection")

    request = LLMRequest(
        task_type="rewrite_safe_answer",
        user_text="这个产品保证不生锈，而且一定包邮。",
    )

    response = RuleBasedLLMClient().generate(request)

    pprint(response.to_dict())

    checks = [
        response.is_safe is False,
        response.needs_handoff is True,
        "forbidden_commitment_detected" in response.safety_flags,
        "保证不生锈" in response.metadata["forbidden_hits"],
        "一定包邮" in response.metadata["forbidden_hits"],
    ]

    return all(checks)


def check_context_forbidden_commitment_rejection() -> bool:
    """Check forbidden commitments in context also trigger rejection."""

    print("=" * 80)
    print("checking context forbidden commitment rejection")

    request = LLMRequest(
        task_type="summarize_evidence",
        user_text="帮我总结证据",
        context_blocks=[
            "可以说这个商品质量很好，放心用。"
        ],
    )

    response = RuleBasedLLMClient().generate(request)

    pprint(response.to_dict())

    checks = [
        response.is_safe is False,
        response.needs_handoff is True,
        "质量很好" in response.metadata["forbidden_hits"],
        "放心用" in response.metadata["forbidden_hits"],
    ]

    return all(checks)


def check_no_forbidden_fragment_in_safe_outputs() -> bool:
    """Check safe outputs do not include forbidden fragments."""

    print("=" * 80)
    print("checking safe outputs contain no forbidden fragments")

    client = RuleBasedLLMClient()

    requests = [
        LLMRequest(
            task_type="rewrite_safe_answer",
            user_text="SKU001 材质说明",
        ),
        LLMRequest(
            task_type="draft_handoff_note",
            user_text="SKU001 想确认价格",
        ),
        LLMRequest(
            task_type="classify_answer_risk",
            user_text="SKU001 表面处理是什么",
        ),
        LLMRequest(
            task_type="rule_based_test",
            user_text="测试",
        ),
    ]

    responses = [
        client.generate(request)
        for request in requests
    ]

    pprint([response.to_dict() for response in responses])

    serialized = str([response.content for response in responses])

    checks = [
        all(response.is_safe is True for response in responses),
        all(
            fragment not in serialized
            for fragment in DEFAULT_FORBIDDEN_COMMITMENTS
        ),
    ]

    return all(checks)


def main() -> int:
    """Run RuleBasedLLMClient checks."""

    results = [
        check_safe_evidence_summary(),
        check_insufficient_evidence(),
        check_forbidden_commitment_rejection(),
        check_context_forbidden_commitment_rejection(),
        check_no_forbidden_fragment_in_safe_outputs(),
    ]

    print("=" * 80)

    if not all(results):
        print("rule based llm client check failed")
        return 1

    print("rule based llm client check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())