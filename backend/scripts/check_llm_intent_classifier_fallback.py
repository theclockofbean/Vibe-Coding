# ruff: noqa: E402,I001
"""Check LLM intent classifier fallback."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from pprint import pprint
from typing import Final
from collections.abc import Iterator

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.llm.intent_classifier import (
    ALLOWED_INTENTS,
    LLMIntentClassifier,
    classify_intent_by_keywords,
    parse_llm_intent_content,
)


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


def check_keyword_fallback() -> bool:
    """Check local keyword fallback."""

    print("=" * 80)
    print("checking keyword fallback")

    cases = [
        ("SKU001 螺纹规格是多少", "spec"),
        ("SKU001 多少钱", "price"),
        ("SKU001 几天发货", "logistics"),
        ("这款铝合金的质量怎么样", "quality"),
        ("我要人工客服", "escalation"),
    ]

    results = []

    for user_text, expected_intent in cases:
        result = classify_intent_by_keywords(user_text)
        pprint(result.to_dict())
        results.append(
            result.intent == expected_intent
            and result.intent in ALLOWED_INTENTS
            and result.used_llm is False
        )

    return all(results)


def check_high_confidence_rule_based_skip_llm() -> bool:
    """Check high-confidence rule-based result skips LLM."""

    print("=" * 80)
    print("checking high-confidence rule-based skip")

    classifier = LLMIntentClassifier()

    with patched_env(
        {
            "LLM_ENABLE_REAL_API": "1",
            "LLM_PROVIDER": "deepseek",
            "LLM_BASE_URL": "https://api.deepseek.com",
            "LLM_API_KEY": "TestAPI",
            "LLM_MODEL": "deepseek-v4-flash",
        }
    ):
        result = classifier.classify(
            user_text="这款铝合金的质量怎么样",
            rule_based_intent="quality",
            rule_based_confidence=0.91,
        )

    pprint(result.to_dict())

    checks = [
        result.intent == "quality",
        result.used_llm is False,
        result.fallback_reason == "rule_based_high_confidence",
    ]

    return all(checks)


def check_disabled_real_api_fallback() -> bool:
    """Check real API disabled fallback."""

    print("=" * 80)
    print("checking disabled real API fallback")

    classifier = LLMIntentClassifier()

    with patched_env(
        {
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        result = classifier.classify(
            user_text="这款铝合金的质量怎么样",
            rule_based_intent="general",
            rule_based_confidence=0.2,
        )

    pprint(result.to_dict())

    checks = [
        result.intent == "quality",
        result.used_llm is False,
        result.fallback_reason == "real_api_disabled",
    ]

    return all(checks)


def check_parse_llm_intent_content() -> bool:
    """Check LLM intent JSON parser."""

    print("=" * 80)
    print("checking LLM intent parser")

    valid_json = '{"intent": "quality", "confidence": 0.88, "reason": "询问质量"}'
    valid_fenced = '```json\n{"intent": "price", "confidence": 0.77, "reason": "询价"}\n```'
    invalid_json = '{"intent": "unknown", "confidence": 0.9}'

    parsed_json = parse_llm_intent_content(valid_json)
    parsed_fenced = parse_llm_intent_content(valid_fenced)
    parsed_invalid = parse_llm_intent_content(invalid_json)

    pprint(
        {
            "parsed_json": parsed_json.to_dict() if parsed_json else None,
            "parsed_fenced": parsed_fenced.to_dict() if parsed_fenced else None,
            "parsed_invalid": parsed_invalid,
        }
    )

    checks = [
        parsed_json is not None and parsed_json.intent == "quality",
        parsed_fenced is not None and parsed_fenced.intent == "price",
        parsed_invalid is None,
    ]

    return all(checks)


def check_real_api_if_configured() -> bool:
    """Check real API classifier path when env is ready."""

    print("=" * 80)
    print("checking real API intent classifier path if configured")

    if not real_api_env_ready():
        print("real API intent classifier skipped: env missing or placeholder")
        return True

    classifier = LLMIntentClassifier()

    result = classifier.classify(
        user_text="SKU001 这款铝合金的质量怎么样？会不会容易掉漆？",
        rule_based_intent="general",
        rule_based_confidence=0.2,
    )

    pprint(result.to_dict())

    checks = [
        result.intent == "quality",
        result.used_llm is True,
        result.is_valid is True,
        result.fallback_reason is None,
        result.metadata.get("provider") == os.getenv("LLM_PROVIDER"),
        result.metadata.get("model") == os.getenv("LLM_MODEL"),
    ]

    return all(checks)


def real_api_env_ready() -> bool:
    """Return whether real API env vars are ready."""

    enabled = os.getenv("LLM_ENABLE_REAL_API", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    provider = os.getenv("LLM_PROVIDER", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()

    return (
        enabled
        and bool(provider)
        and bool(base_url)
        and bool(model)
        and api_key.lower() not in PLACEHOLDER_API_KEYS
    )


@contextmanager
def patched_env(
    values: dict[str, str],
) -> Iterator[None]:
    """Temporarily patch LLM env vars."""

    old_values = {
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
        check_keyword_fallback(),
        check_high_confidence_rule_based_skip_llm(),
        check_disabled_real_api_fallback(),
        check_parse_llm_intent_content(),
        check_real_api_if_configured(),
    ]

    print("=" * 80)

    if not all(results):
        print("LLM intent classifier fallback check failed")
        return 1

    print("LLM intent classifier fallback check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())