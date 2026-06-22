"""LLM client factory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from app.agent.llm.client import LLMClient, RuleBasedLLMClient
from app.agent.llm.openai_compatible import (
    OpenAICompatibleLLMClient,
    OpenAICompatibleLLMConfig,
)


@dataclass(frozen=True)
class LLMClientBuildResult:
    """LLM client factory result."""

    client: LLMClient
    provider: str
    real_api_enabled: bool
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_llm_client_from_env() -> LLMClient:
    """Build LLMClient from environment."""
    return build_llm_client_result_from_env().client


def build_llm_client_result_from_env() -> LLMClientBuildResult:
    """Build LLMClient with metadata from environment."""

    real_api_enabled = _env_bool("LLM_ENABLE_REAL_API", default=False)

    if not real_api_enabled:
        return LLMClientBuildResult(
            client=RuleBasedLLMClient(),
            provider="rule_based",
            real_api_enabled=False,
            warnings=[],
            metadata={
                "factory": "LLMClientFactory",
                "real_api_enabled": False,
                "fallback_reason": "real_api_disabled",
            },
        )

    config = OpenAICompatibleLLMConfig.from_env()

    if config.provider == "rule_based":
        return LLMClientBuildResult(
            client=RuleBasedLLMClient(),
            provider="rule_based",
            real_api_enabled=False,
            warnings=["LLM_PROVIDER is rule_based"],
            metadata={
                "factory": "LLMClientFactory",
                "real_api_enabled": False,
                "fallback_reason": "provider_rule_based",
            },
        )

    if not config.is_complete():
        return LLMClientBuildResult(
            client=RuleBasedLLMClient(),
            provider="rule_based",
            real_api_enabled=False,
            warnings=["real LLM API config is incomplete"],
            metadata={
                "factory": "LLMClientFactory",
                "real_api_enabled": False,
                "fallback_reason": "real_api_config_incomplete",
                "base_url_configured": bool(config.base_url),
                "api_key_configured": bool(config.api_key),
                "model_configured": bool(config.model),
            },
        )

    return LLMClientBuildResult(
        client=OpenAICompatibleLLMClient(config=config),
        provider=config.provider,
        real_api_enabled=True,
        warnings=[],
        metadata={
            "factory": "LLMClientFactory",
            "real_api_enabled": True,
            "provider": config.provider,
            "model": config.model,
            "base_url_configured": bool(config.base_url),
            "api_key_configured": bool(config.api_key),
        },
    )


def _env_bool(
    key: str,
    *,
    default: bool,
) -> bool:
    """Read boolean env var."""
    value = os.getenv(key)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_llm_client():
    """
    兼容旧调用入口（RAG / Answer Service）
    实际统一走 env factory
    """
    return build_llm_client_from_env()
