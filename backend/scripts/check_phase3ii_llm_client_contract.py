# ruff: noqa: E402,I001
"""Check Phase 3-I-I LLM client contract without calling external APIs."""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.openai_compatible import OpenAICompatibleLLMClient
from app.agent.llm.openai_compatible import OpenAICompatibleLLMConfig
from app.agent.llm.schemas import LLMRequest
from app.agent.llm.schemas import LLMResponse


SENSITIVE_ENV_NAMES: Final[tuple[str, ...]] = (
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "QWEN_API_KEY",
    "ANTHROPIC_API_KEY",
)


LLM_ENV_NAMES: Final[tuple[str, ...]] = (
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LLM_TEMPERATURE",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "QWEN_API_KEY",
    "ANTHROPIC_API_KEY",
)


def main() -> int:
    """Run LLM client contract check."""

    print("=" * 80)
    print("checking Phase 3-I-I LLM client contract")

    errors: list[str] = []

    config_result = inspect_config(errors=errors)
    client_result = inspect_client(errors=errors)
    schema_result = inspect_schemas(errors=errors)
    env_result = inspect_llm_env()

    result = {
        "config_result": config_result,
        "client_result": client_result,
        "schema_result": schema_result,
        "env_result": env_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I LLM client contract check failed")
        return 1

    print("Phase 3-I-I LLM client contract check passed")
    return 0


def inspect_config(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect OpenAI-compatible config contract."""

    result: dict[str, Any] = {
        "class": OpenAICompatibleLLMConfig.__name__,
        "has_from_env": hasattr(OpenAICompatibleLLMConfig, "from_env"),
        "has_is_complete": hasattr(OpenAICompatibleLLMConfig, "is_complete"),
        "has_chat_completions_url": hasattr(
            OpenAICompatibleLLMConfig,
            "chat_completions_url",
        ),
        "init_signature": str(inspect.signature(OpenAICompatibleLLMConfig)),
    }

    if not result["has_from_env"]:
        errors.append("OpenAICompatibleLLMConfig.from_env missing")

    if not result["has_is_complete"]:
        errors.append("OpenAICompatibleLLMConfig.is_complete missing")

    if not result["has_chat_completions_url"]:
        errors.append("OpenAICompatibleLLMConfig.chat_completions_url missing")

    try:
        config = OpenAICompatibleLLMConfig.from_env()
        result["from_env_type"] = type(config).__name__
        result["from_env_public_fields"] = sanitize_object_dict(config)
        result["is_complete"] = bool(config.is_complete())
        result["chat_completions_url"] = (
            config.chat_completions_url() if config.is_complete() else None
        )
    except Exception as exc:  # noqa: BLE001
        result["from_env_error"] = f"{type(exc).__name__}: {exc}"

    return result


def inspect_client(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect OpenAI-compatible client contract."""

    result: dict[str, Any] = {
        "class": OpenAICompatibleLLMClient.__name__,
        "init_signature": str(inspect.signature(OpenAICompatibleLLMClient)),
        "generate_signature": str(
            inspect.signature(OpenAICompatibleLLMClient.generate)
        ),
        "has_generate": hasattr(OpenAICompatibleLLMClient, "generate"),
    }

    if not result["has_generate"]:
        errors.append("OpenAICompatibleLLMClient.generate missing")

    return result


def inspect_schemas(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect LLM request/response schema contracts."""

    result: dict[str, Any] = {
        "LLMRequest": {
            "init_signature": str(inspect.signature(LLMRequest)),
            "has_to_dict": hasattr(LLMRequest, "to_dict"),
            "annotations": dict(getattr(LLMRequest, "__annotations__", {})),
        },
        "LLMResponse": {
            "init_signature": str(inspect.signature(LLMResponse)),
            "has_to_dict": hasattr(LLMResponse, "to_dict"),
            "annotations": dict(getattr(LLMResponse, "__annotations__", {})),
        },
    }

    if not result["LLMRequest"]["has_to_dict"]:
        errors.append("LLMRequest.to_dict missing")

    if not result["LLMResponse"]["has_to_dict"]:
        errors.append("LLMResponse.to_dict missing")

    return result


def inspect_llm_env() -> dict[str, Any]:
    """Inspect LLM env readiness without exposing secrets."""

    env_values: dict[str, Any] = {}

    for name in LLM_ENV_NAMES:
        raw_value = os.environ.get(name)
        env_values[name] = mask_env_value(name=name, value=raw_value)

    return {
        "env_values": env_values,
        "has_any_api_key": any(os.environ.get(name) for name in SENSITIVE_ENV_NAMES),
        "has_llm_base_url": bool(os.environ.get("LLM_BASE_URL")),
        "has_llm_model": bool(os.environ.get("LLM_MODEL")),
    }


def sanitize_object_dict(
    value: object,
) -> dict[str, Any]:
    """Return public object fields with secrets masked."""

    raw_dict = getattr(value, "__dict__", {})
    result: dict[str, Any] = {}

    if not isinstance(raw_dict, dict):
        return result

    for key, item in raw_dict.items():
        result[str(key)] = mask_env_value(name=str(key), value=item)

    return result


def mask_env_value(
    *,
    name: str,
    value: object,
) -> object:
    """Mask sensitive values."""

    if value is None:
        return None

    if any(token in name.upper() for token in ("KEY", "SECRET", "TOKEN")):
        text = str(value)

        if not text:
            return ""

        return f"***masked***len={len(text)}"

    return value


if __name__ == "__main__":
    raise SystemExit(main())