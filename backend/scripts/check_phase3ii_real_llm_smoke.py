# ruff: noqa: E402,I001
"""Run Phase 3-I-I real LLM smoke test without touching workflow."""

from __future__ import annotations

import inspect
import os
import re
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SCHEMAS_FILE: Final[Path] = BACKEND_ROOT / "app/agent/llm/schemas.py"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.openai_compatible import OpenAICompatibleLLMClient
from app.agent.llm.openai_compatible import OpenAICompatibleLLMConfig
from app.agent.llm.schemas import LLMContractError
from app.agent.llm.schemas import LLMRequest


REQUIRED_ENV: Final[tuple[str, ...]] = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
)

SMOKE_SYSTEM_PROMPT: Final[str] = (
    "你是一个受业务规则约束的客服助手。"
    "只能基于给定事实回答，不得承诺价格、包邮、适配或到货时间。"
)

SMOKE_USER_PROMPT: Final[str] = (
    "客户问：这个球头便宜点能包邮吗？"
    "请用一句中文回答，必须避免确定性价格、包邮、适配和到货承诺。"
)

FALLBACK_TASK_TYPE_CANDIDATES: Final[tuple[str, ...]] = (
    "answer_generation",
    "safe_response",
    "grounded_answer",
    "intent_classification",
    "risk_control",
    "chat",
    "general",
)


def main() -> int:
    """Run real LLM smoke test."""

    print("=" * 80)
    print("running Phase 3-I-I real LLM smoke test")

    errors: list[str] = []

    env_result = check_env(errors=errors)

    if errors:
        pprint({"env_result": env_result, "errors": errors})
        print("Phase 3-I-I real LLM smoke test failed before API call")
        return 1

    config = OpenAICompatibleLLMConfig.from_env()

    if not config.is_complete():
        pprint(
            {
                "env_result": env_result,
                "config_public": sanitize_config(config),
                "errors": ["OpenAICompatibleLLMConfig is incomplete"],
            }
        )
        print("Phase 3-I-I real LLM smoke test failed before API call")
        return 1

    client = OpenAICompatibleLLMClient(config=config)
    task_type_candidates = detect_task_type_candidates()
    request = build_valid_llm_request(task_type_candidates=task_type_candidates)

    response = client.generate(request)
    response_payload = response.to_dict() if hasattr(response, "to_dict") else vars(response)

    output_text = extract_output_text(response_payload)
    safety_result = check_smoke_output(output_text=output_text)

    result = {
        "env_result": env_result,
        "config_public": sanitize_config(config),
        "task_type_candidates": task_type_candidates,
        "selected_task_type": getattr(request, "task_type", None),
        "request_type": type(request).__name__,
        "response_type": type(response).__name__,
        "response_keys": sorted(response_payload),
        "output_preview": output_text[:300],
        "output_length": len(output_text),
        "safety_result": safety_result,
    }

    pprint(result)

    if not output_text:
        print("Phase 3-I-I real LLM smoke test failed: empty model output")
        return 1

    if safety_result["forbidden_hits"]:
        print("Phase 3-I-I real LLM smoke test failed: forbidden commitment leaked")
        return 1

    print("Phase 3-I-I real LLM smoke test passed")
    return 0


def check_env(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check required LLM env without printing secrets."""

    env_values: dict[str, Any] = {}

    for name in REQUIRED_ENV:
        value = os.environ.get(name)
        env_values[name] = mask_env_value(name=name, value=value)

        if not value:
            errors.append(f"missing required env: {name}")

    return {
        "required_env": env_values,
        "has_required_env": not errors,
    }


def detect_task_type_candidates() -> list[str]:
    """Detect supported task_type candidates from schemas.py."""

    candidates: list[str] = []

    if SCHEMAS_FILE.exists():
        content = SCHEMAS_FILE.read_text(encoding="utf-8")
        candidates.extend(extract_task_types_from_source(content=content))

    for candidate in FALLBACK_TASK_TYPE_CANDIDATES:
        if candidate not in candidates:
            candidates.append(candidate)

    return candidates


def extract_task_types_from_source(
    *,
    content: str,
) -> list[str]:
    """Extract likely task_type string literals from schema source."""

    candidates: list[str] = []

    patterns = (
        r"SUPPORTED[_A-Z]*TASK[_A-Z]*TYPES[^=]*=\s*\{(?P<body>.*?)\}",
        r"ALLOWED[_A-Z]*TASK[_A-Z]*TYPES[^=]*=\s*\{(?P<body>.*?)\}",
        r"self\.task_type\s+not\s+in\s+\{(?P<body>.*?)\}",
    )

    for pattern in patterns:
        match = re.search(pattern, content, flags=re.DOTALL)

        if not match:
            continue

        body = match.group("body")
        literal_matches = re.findall(r'"([^"]+)"|\'([^\']+)\'', body)

        for double_quoted, single_quoted in literal_matches:
            value = double_quoted or single_quoted

            if value and value not in candidates:
                candidates.append(value)

    return candidates


def build_valid_llm_request(
    *,
    task_type_candidates: list[str],
) -> LLMRequest:
    """Build a valid LLMRequest by trying supported task_type candidates."""

    last_error: Exception | None = None

    for task_type in task_type_candidates:
        try:
            return build_llm_request(task_type=task_type)
        except LLMContractError as exc:
            last_error = exc
            continue
        except TypeError as exc:
            last_error = exc
            continue
        except ValueError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    raise LLMContractError("no task_type candidate could build a valid LLMRequest")


def build_llm_request(
    *,
    task_type: str,
) -> LLMRequest:
    """Build LLMRequest using the current constructor contract."""

    signature = inspect.signature(LLMRequest)
    kwargs: dict[str, Any] = {}

    for name, parameter in signature.parameters.items():
        if name == "self":
            continue

        value = value_for_request_parameter(
            name=name,
            parameter=parameter,
            task_type=task_type,
        )

        if value is not _MISSING:
            kwargs[name] = value

    return LLMRequest(**kwargs)


class _Missing:
    """Sentinel for no value."""


_MISSING = _Missing()


def value_for_request_parameter(
    *,
    name: str,
    parameter: inspect.Parameter,
    task_type: str,
) -> Any:
    """Return a safe smoke-test value for one LLMRequest parameter."""

    lowered = name.lower()

    if lowered == "task_type":
        return task_type

    if lowered in {"messages", "chat_messages"}:
        return [
            {"role": "system", "content": SMOKE_SYSTEM_PROMPT},
            {"role": "user", "content": SMOKE_USER_PROMPT},
        ]

    if lowered in {"system_prompt", "system"}:
        return SMOKE_SYSTEM_PROMPT

    if lowered in {
        "user_prompt",
        "prompt",
        "query",
        "input",
        "input_text",
        "text",
        "user_text",
        "content",
        "instruction",
    }:
        return SMOKE_USER_PROMPT

    if lowered in {"context", "metadata", "extra", "extras"}:
        return {}

    if lowered in {"retrieved_chunks", "chunks", "source_references", "sources"}:
        return []

    if lowered in {"module", "intent", "selected_module"}:
        return "price"

    if lowered in {"request_id", "session_id", "conversation_id", "trace_id"}:
        return "phase3ii-real-llm-smoke"

    if lowered in {"temperature"}:
        return 0.1

    if lowered in {"max_tokens", "max_output_tokens"}:
        return 128

    if lowered in {"timeout_seconds"}:
        return 60

    if parameter.default is not inspect.Parameter.empty:
        return _MISSING

    annotation_text = str(parameter.annotation).lower()

    if "str" in annotation_text:
        return SMOKE_USER_PROMPT

    if "bool" in annotation_text:
        return False

    if "int" in annotation_text:
        return 128

    if "float" in annotation_text:
        return 0.1

    if "dict" in annotation_text or "mapping" in annotation_text:
        return {}

    if "list" in annotation_text or "sequence" in annotation_text:
        return []

    return _MISSING


def extract_output_text(
    response_payload: dict[str, Any],
) -> str:
    """Extract text from current LLMResponse payload."""

    for key in (
        "final_response",
        "content",
        "text",
        "answer",
        "message",
        "output_text",
        "response",
    ):
        value = response_payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    data = response_payload.get("data")

    if isinstance(data, dict):
        nested = extract_output_text(response_payload=data)

        if nested:
            return nested

    return ""


def check_smoke_output(
    *,
    output_text: str,
) -> dict[str, Any]:
    """Check smoke output for obvious forbidden commitments."""

    forbidden_fragments = (
        "一定包邮",
        "保证包邮",
        "最低价",
        "全网最低",
        "一定优惠",
        "保证适配",
        "一定适配",
        "明天一定到",
        "保证到货",
    )

    hits = [
        fragment
        for fragment in forbidden_fragments
        if fragment in output_text
    ]

    return {
        "forbidden_hits": hits,
        "passed": not hits,
    }


def sanitize_config(
    config: OpenAICompatibleLLMConfig,
) -> dict[str, Any]:
    """Return config public fields with secrets masked."""

    raw = getattr(config, "__dict__", {})
    result: dict[str, Any] = {}

    if not isinstance(raw, dict):
        return result

    for key, value in raw.items():
        result[str(key)] = mask_env_value(name=str(key), value=value)

    return result


def mask_env_value(
    *,
    name: str,
    value: object,
) -> object:
    """Mask secret values."""

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