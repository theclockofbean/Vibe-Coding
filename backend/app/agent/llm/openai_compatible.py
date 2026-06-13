"""OpenAI-compatible LLM client.

This client supports DeepSeek / OpenAI-compatible chat completions APIs through
httpx. It never stores or exposes API keys in LLMResponse metadata.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.agent.llm.prompts import build_openai_compatible_messages
from app.agent.llm.schemas import LLMRequest, LLMResponse


class OpenAICompatibleLLMError(RuntimeError):
    """OpenAI-compatible LLM error."""


@dataclass(frozen=True)
class OpenAICompatibleLLMConfig:
    """OpenAI-compatible client config."""

    provider: str = "openai_compatible"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 2
    default_temperature: float = 0.2
    default_max_tokens: int = 800

    @classmethod
    def from_env(cls) -> OpenAICompatibleLLMConfig:
        """Build config from environment variables."""

        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai_compatible").strip()
            or "openai_compatible",
            base_url=_optional_env("LLM_BASE_URL"),
            api_key=_optional_env("LLM_API_KEY"),
            model=_optional_env("LLM_MODEL"),
            timeout_seconds=_float_env("LLM_TIMEOUT_SECONDS", 30.0),
            max_retries=_int_env("LLM_MAX_RETRIES", 2),
            default_temperature=_float_env("LLM_TEMPERATURE", 0.2),
            default_max_tokens=_int_env("LLM_MAX_TOKENS", 800),
        )

    def is_complete(self) -> bool:
        """Return whether real API config is complete."""

        return bool(self.base_url and self.api_key and self.model)

    def chat_completions_url(self) -> str:
        """Return chat completions endpoint URL."""

        if not self.base_url:
            raise OpenAICompatibleLLMError("LLM_BASE_URL is missing")

        base_url = self.base_url.rstrip("/")

        if base_url.endswith("/chat/completions"):
            return base_url

        return f"{base_url}/chat/completions"


class OpenAICompatibleLLMClient:
    """LLMClient implementation for OpenAI-compatible APIs."""

    def __init__(
        self,
        *,
        config: OpenAICompatibleLLMConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    @property
    def config(self) -> OpenAICompatibleLLMConfig:
        """Return config."""

        return self._config

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        """Generate LLM response."""

        start = time.perf_counter()

        if not self._config.is_complete():
            return self._build_error_response(
                request=request,
                error="real LLM API config is incomplete",
                latency_ms=_elapsed_ms(start),
            )

        payload = self._build_payload(request)
        last_error = ""

        attempt_count = max(1, self._config.max_retries + 1)

        for attempt_index in range(attempt_count):
            try:
                data = self._post_chat_completions(payload)
                return self._build_success_response(
                    request=request,
                    data=data,
                    latency_ms=_elapsed_ms(start),
                    attempt_index=attempt_index,
                )
            except (httpx.HTTPError, OpenAICompatibleLLMError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

        return self._build_error_response(
            request=request,
            error=last_error or "unknown OpenAI-compatible LLM error",
            latency_ms=_elapsed_ms(start),
        )

    def _build_payload(
        self,
        request: LLMRequest,
    ) -> dict[str, Any]:
        """Build chat completions request payload."""

        return {
            "model": self._config.model,
            "messages": build_openai_compatible_messages(request),
            "temperature": request.temperature
            if request.temperature is not None
            else self._config.default_temperature,
            "max_tokens": request.max_tokens
            if request.max_tokens is not None
            else self._config.default_max_tokens,
        }

    def _post_chat_completions(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Post payload to chat completions API."""

        headers = {
            "Authorization": f"Bearer {self._config.api_key or ''}",
            "Content-Type": "application/json",
        }

        with httpx.Client(
            timeout=self._config.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = client.post(
                self._config.chat_completions_url(),
                headers=headers,
                json=dict(payload),
            )

        if response.status_code >= 400:
            raise OpenAICompatibleLLMError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        data = response.json()

        if not isinstance(data, dict):
            raise OpenAICompatibleLLMError("LLM response is not a JSON object")

        return {
            str(key): value
            for key, value in data.items()
        }

    def _build_success_response(
        self,
        *,
        request: LLMRequest,
        data: Mapping[str, Any],
        latency_ms: int,
        attempt_index: int,
    ) -> LLMResponse:
        """Build success LLMResponse."""

        content = _extract_content(data)

        if not content:
            raise OpenAICompatibleLLMError("LLM response content is empty")

        usage = _dict_value(data.get("usage"))
        finish_reason = _extract_finish_reason(data)

        return LLMResponse(
            request_id=request.request_id,
            provider=self._config.provider,
            model=self._config.model or "unknown",
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            safety_flags=[],
            is_safe=True,
            needs_handoff=False,
            metadata={
                "real_api": True,
                "task_type": request.task_type,
                "attempt_index": attempt_index,
                "api_key_configured": bool(self._config.api_key),
                "base_url_configured": bool(self._config.base_url),
                "final_response_allowed": False,
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
            error=None,
        )

    def _build_error_response(
        self,
        *,
        request: LLMRequest,
        error: str,
        latency_ms: int,
    ) -> LLMResponse:
        """Build error LLMResponse."""

        return LLMResponse(
            request_id=request.request_id,
            provider=self._config.provider,
            model=self._config.model or "unknown",
            content="",
            finish_reason="error",
            usage={},
            latency_ms=latency_ms,
            safety_flags=["llm_api_error"],
            is_safe=False,
            needs_handoff=False,
            metadata={
                "real_api": True,
                "task_type": request.task_type,
                "api_key_configured": bool(self._config.api_key),
                "base_url_configured": bool(self._config.base_url),
                "final_response_allowed": False,
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
            error=error,
        )


def _extract_content(
    data: Mapping[str, Any],
) -> str:
    """Extract assistant content."""

    choices = data.get("choices")

    if not isinstance(choices, list) or not choices:
        raise OpenAICompatibleLLMError("LLM response choices is empty")

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise OpenAICompatibleLLMError("LLM response choice is not an object")

    message = first_choice.get("message")

    if not isinstance(message, dict):
        raise OpenAICompatibleLLMError("LLM response message is not an object")

    content = message.get("content")

    if not isinstance(content, str):
        raise OpenAICompatibleLLMError("LLM response content is not text")

    return content.strip()


def _extract_finish_reason(
    data: Mapping[str, Any],
) -> str:
    """Extract finish reason."""

    choices = data.get("choices")

    if not isinstance(choices, list) or not choices:
        return "unknown"

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        return "unknown"

    finish_reason = first_choice.get("finish_reason")

    if not isinstance(finish_reason, str):
        return "unknown"

    return finish_reason


def _dict_value(
    value: object,
) -> dict[str, Any]:
    """Return dict value with string keys."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _optional_env(
    key: str,
) -> str | None:
    """Read optional env var."""

    value = os.getenv(key)

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    return value


def _float_env(
    key: str,
    default: float,
) -> float:
    """Read float env var."""

    value = os.getenv(key)

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _int_env(
    key: str,
    default: int,
) -> int:
    """Read int env var."""

    value = os.getenv(key)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _elapsed_ms(
    start: float,
) -> int:
    """Return elapsed milliseconds."""

    return int((time.perf_counter() - start) * 1000)