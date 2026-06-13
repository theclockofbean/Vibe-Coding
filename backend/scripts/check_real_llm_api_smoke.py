# ruff: noqa: E402,I001
"""Real LLM API smoke check.

This script calls the real OpenAI-compatible LLM API only when all real API
environment variables are configured and the API key is not a placeholder.

With placeholder keys such as TestAPI, this script skips the network call and
passes safely.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.openai_compatible import (
    OpenAICompatibleLLMClient,
    OpenAICompatibleLLMConfig,
)
from app.agent.llm.safety import LLMSafetyGuard
from app.agent.llm.schemas import LLMRequest


PLACEHOLDER_API_KEYS: Final[set[str]] = {
    "",
    "test",
    "testapi",
    "test_api",
    "your_api_key",
    "your-api-key",
    "replace_me",
    "placeholder",
}


FORBIDDEN_COMMITMENT_FRAGMENTS: Final[tuple[str, ...]] = (
    "保证最低价",
    "最低价给你",
    "一定包邮",
    "保证到货",
    "今天一定发",
    "保证不坏",
    "保证不生锈",
    "保证不掉漆",
    "保证耐用",
    "能用几年",
    "一年质保",
    "终身质保",
    "七天无理由",
    "一定能退",
    "一定能换",
    "一定赔",
    "一定补发",
    "质量很好",
    "放心用",
    "完全没问题",
)


def build_smoke_request() -> LLMRequest:
    """Build safe real API smoke request."""

    return LLMRequest(
        request_id="real-llm-api-smoke-check",
        task_type="summarize_evidence",
        user_text="SKU001 这款铝合金的质量怎么样？",
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "summary": (
                    "铝合金 6061 常用于轻量化零件；"
                    "该说明仅作为材料常识补充，不构成质量承诺。"
                ),
                "allow_answer_reference": True,
                "allow_commitment_reference": False,
            },
            {
                "chunk_id": "seed_quality_anodized_surface",
                "summary": (
                    "阳极氧化黑色是常见表面处理方式；"
                    "具体外观和耐久表现需以检测记录或人工确认为准。"
                ),
                "allow_answer_reference": True,
                "allow_commitment_reference": False,
            },
        ],
        structured_facts={
            "sku_id": "SKU001",
            "product_name": "铝合金竞技换挡球头",
            "material": "铝合金6061",
            "surface_treatment": "阳极氧化黑色",
        },
        business_rules=[
            "质量类问题不得生成绝对化质量承诺。",
            "不得承诺不坏、不生锈、不掉漆、耐久年限或质保。",
            "RAG 只能作为补充说明，不作为业务承诺来源。",
            "检测记录缺失时，必须说明需要人工确认。",
        ],
        metadata={
            "check": "real_llm_api_smoke",
            "final_response_allowed": False,
            "fact_source_allowed": False,
            "commitment_source_allowed": False,
        },
    )


def should_skip_real_api(
    config: OpenAICompatibleLLMConfig,
) -> tuple[bool, str]:
    """Return whether real API smoke should be skipped."""

    if os.getenv("LLM_ENABLE_REAL_API", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True, "LLM_ENABLE_REAL_API is not enabled"

    if not config.base_url:
        return True, "LLM_BASE_URL is missing"

    if not config.model:
        return True, "LLM_MODEL is missing"

    api_key = (config.api_key or "").strip()

    if api_key.lower() in PLACEHOLDER_API_KEYS:
        return True, "LLM_API_KEY is placeholder or missing"

    return False, ""


def check_real_api_smoke() -> bool:
    """Run real API smoke check when configured."""

    print("=" * 80)
    print("checking real LLM API smoke")

    config = OpenAICompatibleLLMConfig.from_env()

    print(
        {
            "provider": config.provider,
            "base_url_configured": bool(config.base_url),
            "api_key_configured": bool(config.api_key),
            "model": config.model,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
        }
    )

    should_skip, skip_reason = should_skip_real_api(config)

    if should_skip:
        print(f"real LLM API smoke skipped: {skip_reason}")
        return True

    client = OpenAICompatibleLLMClient(config=config)
    request = build_smoke_request()

    response = client.generate(request)
    guarded_response = LLMSafetyGuard().guard_response(response)

    response_dict = guarded_response.to_dict()
    pprint(response_dict)

    serialized = json.dumps(response_dict, ensure_ascii=False)

    if config.api_key and config.api_key in serialized:
        print("failed: API key leaked into response serialization")
        return False

    if guarded_response.error is not None:
        print(f"failed: real API returned error: {guarded_response.error}")
        return False

    if not guarded_response.content.strip():
        print("failed: real API content is empty")
        return False

    if guarded_response.is_safe is not True:
        print("failed: guarded response is unsafe")
        return False

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in guarded_response.content:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    checks = [
        guarded_response.provider == config.provider,
        guarded_response.model == config.model,
        guarded_response.metadata["final_response_allowed"] is False,
        guarded_response.metadata["fact_source_allowed"] is False,
        guarded_response.metadata["commitment_source_allowed"] is False,
        "铝合金" in guarded_response.content
        or "6061" in guarded_response.content
        or "人工确认" in guarded_response.content,
    ]

    return all(checks)


def main() -> int:
    """Run real API smoke check."""

    passed = check_real_api_smoke()

    print("=" * 80)

    if not passed:
        print("real LLM API smoke check failed")
        return 1

    print("real LLM API smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())