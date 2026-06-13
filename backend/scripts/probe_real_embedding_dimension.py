# ruff: noqa: E402,I001
"""Probe real embedding dimension and write local result.

This script does not create Qdrant collections. It only confirms the real
embedding vector dimension so the next phase can safely create quality_kb_v1.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.real_embedding import (
    OpenAICompatibleEmbeddingClient,
    RealEmbeddingConfig,
    RealEmbeddingError,
    real_embedding_enabled_from_env,
)


PROBE_OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "embedding"
    / "embedding_probe_result.json"
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


def probe_real_embedding_dimension() -> bool:
    """Probe real embedding dimension."""

    print("=" * 80)
    print("probing real embedding dimension")

    config = RealEmbeddingConfig.from_env()

    safe_config = {
        "enabled": real_embedding_enabled_from_env(),
        "provider": config.provider,
        "base_url_configured": bool(config.base_url),
        "api_key_configured": bool(config.api_key),
        "model": config.model,
        "dimension_expected": config.dimension,
        "timeout_seconds": config.timeout_seconds,
        "max_retries": config.max_retries,
    }

    pprint(safe_config)

    should_skip, reason = should_skip_probe(config)

    if should_skip:
        write_probe_result(
            {
                "status": "skipped",
                "reason": reason,
                "provider": config.provider,
                "model": config.model,
                "base_url_configured": bool(config.base_url),
                "api_key_configured": bool(config.api_key),
                "vector_dimension": None,
                "ready_for_quality_collection": False,
            }
        )

        print(f"embedding dimension probe skipped: {reason}")
        return True

    client = OpenAICompatibleEmbeddingClient(config=config)

    texts = [
        "SKU001 铝合金6061 材质说明",
        "SKU001 阳极氧化黑色 表面处理说明",
        "品质问题不得生成质量承诺，检测记录缺失时需人工确认。",
    ]

    try:
        vectors = client.embed_texts(texts)
    except RealEmbeddingError as exc:
        write_probe_result(
            {
                "status": "failed",
                "reason": str(exc),
                "provider": config.provider,
                "model": config.model,
                "base_url_configured": bool(config.base_url),
                "api_key_configured": bool(config.api_key),
                "vector_dimension": None,
                "ready_for_quality_collection": False,
            }
        )

        print(f"embedding dimension probe failed: {exc}")
        return False

    dimensions = sorted({len(vector) for vector in vectors})
    vector_dimension = dimensions[0] if len(dimensions) == 1 else None

    result = {
        "status": "passed" if vector_dimension else "failed",
        "reason": None if vector_dimension else "inconsistent vector dimensions",
        "provider": config.provider,
        "model": config.model,
        "base_url_configured": bool(config.base_url),
        "api_key_configured": bool(config.api_key),
        "text_count": len(texts),
        "vector_count": len(vectors),
        "vector_dimensions": dimensions,
        "vector_dimension": vector_dimension,
        "expected_dimension": config.dimension,
        "ready_for_quality_collection": bool(vector_dimension),
    }

    if config.dimension is not None and vector_dimension != config.dimension:
        result["status"] = "failed"
        result["reason"] = (
            f"dimension mismatch: expected={config.dimension}, "
            f"actual={vector_dimension}"
        )
        result["ready_for_quality_collection"] = False

    write_probe_result(result)

    pprint(result)

    return result["status"] == "passed"


def should_skip_probe(
    config: RealEmbeddingConfig,
) -> tuple[bool, str]:
    """Return whether probe should be skipped."""

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


def write_probe_result(
    payload: dict[str, Any],
) -> None:
    """Write probe result JSON without secrets."""

    PROBE_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    safe_payload = {
        **payload,
        "created_at": datetime.now(UTC).isoformat(),
        "output_file": str(PROBE_OUTPUT_FILE),
    }

    serialized = json.dumps(
        safe_payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    api_key = os.getenv("EMBEDDING_API_KEY", "").strip()

    if api_key and api_key in serialized:
        raise RuntimeError("EMBEDDING_API_KEY would leak into probe result")

    PROBE_OUTPUT_FILE.write_text(serialized + "\n", encoding="utf-8")


def main() -> int:
    """Run probe."""

    passed = probe_real_embedding_dimension()

    print("=" * 80)

    if not passed:
        print("real embedding dimension probe failed")
        return 1

    print("real embedding dimension probe completed")
    print(f"result_file={PROBE_OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())