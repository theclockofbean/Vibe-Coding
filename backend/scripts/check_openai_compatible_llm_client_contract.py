# ruff: noqa: E402,I001
"""Check OpenAI-compatible LLM client contract.

This check uses httpx.MockTransport and does not call a real external API.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from pprint import pprint
from typing import Final
from collections.abc import Iterator

import httpx

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.client import RuleBasedLLMClient
from app.agent.llm.factory import build_llm_client_result_from_env
from app.agent.llm.openai_compatible import (
    OpenAICompatibleLLMClient,
    OpenAICompatibleLLMConfig,
)
from app.agent.llm.schemas import LLMRequest


ENV_KEYS: Final[tuple[str, ...]] = (
    "LLM_ENABLE_REAL_API",
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
)


def build_request() -> LLMRequest:
    """Build sample request."""

    return LLMRequest(
        request_id="openai-compatible-contract-check",
        task_type="summarize_evidence",
        user_text="SKU001 材质说明",
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "summary": "铝合金 6061 的一般说明，不作为质量承诺。",
            }
        ],
        structured_facts={
            "sku_id": "SKU001",
            "material": "铝合金6061",
        },
        business_rules=[
            "质量类问题不得生成绝对化质量承诺。",
        ],
        metadata={
            "check": "openai_compatible_contract",
        },
    )


def success_handler(
    request: httpx.Request,
) -> httpx.Response:
    """Mock successful chat completions response."""

    assert request.headers.get("Authorization") == "Bearer mock-api-key"

    payload = json.loads(request.content.decode("utf-8"))

    assert payload["model"] == "mock-model"
    assert isinstance(payload["messages"], list)
    assert payload["messages"][0]["role"] == "system"

    return httpx.Response(
        status_code=200,
        json={
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "这是基于结构化事实和证据的非承诺性说明。",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
        },
    )


def error_handler(
    request: httpx.Request,
) -> httpx.Response:
    """Mock API error."""

    return httpx.Response(
        status_code=500,
        json={
            "error": {
                "message": "mock server error",
            }
        },
    )


def check_success_response() -> bool:
    """Check success response contract."""

    print("=" * 80)
    print("checking OpenAICompatibleLLMClient success response")

    client = OpenAICompatibleLLMClient(
        config=OpenAICompatibleLLMConfig(
            provider="mock_provider",
            base_url="https://mock-llm.local/v1",
            api_key="mock-api-key",
            model="mock-model",
            timeout_seconds=10,
            max_retries=0,
        ),
        transport=httpx.MockTransport(success_handler),
    )

    response = client.generate(build_request())

    response_dict = response.to_dict()
    pprint(response_dict)

    serialized = json.dumps(response_dict, ensure_ascii=False)

    checks = [
        response.error is None,
        response.provider == "mock_provider",
        response.model == "mock-model",
        response.content == "这是基于结构化事实和证据的非承诺性说明。",
        response.finish_reason == "stop",
        response.is_safe is True,
        response.needs_handoff is False,
        response.metadata["real_api"] is True,
        response.metadata["final_response_allowed"] is False,
        response.metadata["fact_source_allowed"] is False,
        response.metadata["commitment_source_allowed"] is False,
        "mock-api-key" not in serialized,
    ]

    return all(checks)


def check_error_response() -> bool:
    """Check error response contract."""

    print("=" * 80)
    print("checking OpenAICompatibleLLMClient error response")

    client = OpenAICompatibleLLMClient(
        config=OpenAICompatibleLLMConfig(
            provider="mock_provider",
            base_url="https://mock-llm.local/v1",
            api_key="mock-api-key",
            model="mock-model",
            timeout_seconds=10,
            max_retries=0,
        ),
        transport=httpx.MockTransport(error_handler),
    )

    response = client.generate(build_request())

    pprint(response.to_dict())

    checks = [
        response.error is not None,
        response.content == "",
        response.finish_reason == "error",
        response.is_safe is False,
        "llm_api_error" in response.safety_flags,
        response.metadata["real_api"] is True,
    ]

    return all(checks)


def check_incomplete_config_response() -> bool:
    """Check incomplete config safely returns error response."""

    print("=" * 80)
    print("checking incomplete config response")

    client = OpenAICompatibleLLMClient(
        config=OpenAICompatibleLLMConfig(
            provider="mock_provider",
            base_url=None,
            api_key=None,
            model=None,
        ),
    )

    response = client.generate(build_request())

    pprint(response.to_dict())

    checks = [
        response.error == "real LLM API config is incomplete",
        response.is_safe is False,
        response.metadata["api_key_configured"] is False,
        response.metadata["base_url_configured"] is False,
    ]

    return all(checks)


def check_factory_default_rule_based() -> bool:
    """Check factory default fallback."""

    print("=" * 80)
    print("checking factory default rule-based fallback")

    with patched_env(
        {
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        result = build_llm_client_result_from_env()

    pprint(result)

    checks = [
        isinstance(result.client, RuleBasedLLMClient),
        result.provider == "rule_based",
        result.real_api_enabled is False,
        result.metadata["fallback_reason"] == "real_api_disabled",
    ]

    return all(checks)


def check_factory_real_api_config() -> bool:
    """Check factory returns real client when config is complete."""

    print("=" * 80)
    print("checking factory real API config")

    with patched_env(
        {
            "LLM_ENABLE_REAL_API": "1",
            "LLM_PROVIDER": "deepseek",
            "LLM_BASE_URL": "https://mock-llm.local/v1",
            "LLM_API_KEY": "mock-api-key",
            "LLM_MODEL": "mock-model",
        }
    ):
        result = build_llm_client_result_from_env()

    pprint(result)

    checks = [
        isinstance(result.client, OpenAICompatibleLLMClient),
        result.provider == "deepseek",
        result.real_api_enabled is True,
        result.metadata["real_api_enabled"] is True,
        result.metadata["api_key_configured"] is True,
    ]

    return all(checks)


def check_factory_incomplete_config_fallback() -> bool:
    """Check factory fallback when real API config is incomplete."""

    print("=" * 80)
    print("checking factory incomplete config fallback")

    with patched_env(
        {
            "LLM_ENABLE_REAL_API": "1",
            "LLM_PROVIDER": "deepseek",
            "LLM_BASE_URL": "https://mock-llm.local/v1",
            "LLM_API_KEY": "",
            "LLM_MODEL": "mock-model",
        }
    ):
        result = build_llm_client_result_from_env()

    pprint(result)

    checks = [
        isinstance(result.client, RuleBasedLLMClient),
        result.provider == "rule_based",
        result.real_api_enabled is False,
        result.metadata["fallback_reason"] == "real_api_config_incomplete",
        result.metadata["api_key_configured"] is False,
    ]

    return all(checks)


@contextmanager
def patched_env(
    values: dict[str, str],
) -> Iterator[None]:
    """Temporarily patch LLM env vars."""

    old_values: dict[str, str | None] = {
        key: os.environ.get(key)
        for key in ENV_KEYS
    }

    try:
        for key in ENV_KEYS:
            os.environ.pop(key, None)

        for key, value in values.items():
            os.environ[key] = value

        yield
    finally:
        for key in ENV_KEYS:
            old_value = old_values[key]

            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def main() -> int:
    """Run checks."""

    results = [
        check_success_response(),
        check_error_response(),
        check_incomplete_config_response(),
        check_factory_default_rule_based(),
        check_factory_real_api_config(),
        check_factory_incomplete_config_fallback(),
    ]

    print("=" * 80)

    if not all(results):
        print("openai-compatible llm client contract check failed")
        return 1

    print("openai-compatible llm client contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())