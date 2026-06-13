# ruff: noqa: E402,I001
"""Smoke check real embedding API.

This script calls the real embedding API only when EMBEDDING_ENABLE_REAL_API=1
and required embedding config is present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.real_embedding import (
    OpenAICompatibleEmbeddingClient,
    RealEmbeddingConfig,
    RealEmbeddingError,
    real_embedding_enabled_from_env,
)


PLACEHOLDER_API_KEYS: Final[set[str]] = {
    "test",
    "testapi",
    "test_api",
    "your_api_key",
    "your-api-key",
    "replace_me",
    "placeholder",
}


def check_real_embedding_smoke() -> bool:
    """Run real embedding smoke check."""

    print("=" * 80)
    print("checking real embedding smoke")

    config = RealEmbeddingConfig.from_env()

    print(
        {
            "enabled": real_embedding_enabled_from_env(),
            "provider": config.provider,
            "base_url_configured": bool(config.base_url),
            "api_key_configured": bool(config.api_key),
            "model": config.model,
            "dimension_expected": config.dimension,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
        }
    )

    should_skip, reason = should_skip_real_embedding(config)

    if should_skip:
        print(f"real embedding smoke skipped: {reason}")
        return True

    client = OpenAICompatibleEmbeddingClient(config=config)

    texts = [
        "SKU001 铝合金6061 材质说明",
        "SKU001 阳极氧化黑色 表面处理说明",
    ]

    try:
        vectors = client.embed_texts(texts)
    except RealEmbeddingError as exc:
        print(f"real embedding smoke failed: {exc}")
        return False

    vector_dimension = len(vectors[0]) if vectors else 0

    result = {
        "provider": config.provider,
        "model": config.model,
        "text_count": len(texts),
        "vector_count": len(vectors),
        "vector_dimension": vector_dimension,
        "first_vector_preview": vectors[0][:5] if vectors else [],
    }

    pprint(result)

    serialized = json.dumps(result, ensure_ascii=False)

    if config.api_key and config.api_key in serialized:
        print("failed: API key leaked into smoke result")
        return False

    checks = [
        len(vectors) == len(texts),
        vector_dimension > 0,
        all(len(vector) == vector_dimension for vector in vectors),
        all(isinstance(value, float) for vector in vectors for value in vector),
    ]

    if config.dimension is not None:
        checks.append(vector_dimension == config.dimension)

    return all(checks)


def should_skip_real_embedding(
    config: RealEmbeddingConfig,
) -> tuple[bool, str]:
    """Return whether smoke should be skipped."""

    if not real_embedding_enabled_from_env():
        return True, "EMBEDDING_ENABLE_REAL_API is not enabled"

    if not config.base_url:
        return True, "EMBEDDING_BASE_URL is missing"

    if not config.model:
        return True, "EMBEDDING_MODEL is missing"

    api_key = config.api_key.strip().lower()

    if api_key in PLACEHOLDER_API_KEYS:
        return True, "EMBEDDING_API_KEY is placeholder"

    return False, ""


def main() -> int:
    """Run smoke check."""

    passed = check_real_embedding_smoke()

    print("=" * 80)

    if not passed:
        print("real embedding smoke check failed")
        return 1

    print("real embedding smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())