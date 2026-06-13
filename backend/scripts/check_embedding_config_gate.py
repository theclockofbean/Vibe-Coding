# ruff: noqa: E402,I001
"""Check embedding config gate before creating quality_kb_v1."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


PROBE_OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "embedding"
    / "embedding_probe_result.json"
)

QUALITY_COLLECTION_NAME: Final[str] = "quality_kb_v1"


def check_embedding_config_gate() -> bool:
    """Check embedding config readiness."""

    print("=" * 80)
    print("checking embedding config gate")

    embedding_enable_real_api = os.getenv("EMBEDDING_ENABLE_REAL_API", "")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "")
    embedding_base_url = os.getenv("EMBEDDING_BASE_URL", "")
    embedding_api_key = os.getenv("EMBEDDING_API_KEY", "")
    embedding_model = os.getenv("EMBEDDING_MODEL", "")
    embedding_dimension_text = os.getenv("EMBEDDING_DIMENSION", "")
    qdrant_collection_quality = os.getenv("QDRANT_COLLECTION_QUALITY", "")

    env_status: dict[str, str | bool] = {
        "EMBEDDING_ENABLE_REAL_API": embedding_enable_real_api,
        "EMBEDDING_PROVIDER": embedding_provider,
        "EMBEDDING_BASE_URL_configured": bool(embedding_base_url),
        "EMBEDDING_API_KEY_configured": bool(embedding_api_key),
        "EMBEDDING_MODEL": embedding_model,
        "EMBEDDING_DIMENSION": embedding_dimension_text,
        "QDRANT_COLLECTION_QUALITY": qdrant_collection_quality,
    }

    probe_result = load_probe_result()
    errors: list[str] = []
    warnings: list[str] = []

    if embedding_enable_real_api.strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        errors.append("EMBEDDING_ENABLE_REAL_API is not enabled")

    if not embedding_provider:
        errors.append("EMBEDDING_PROVIDER is missing")

    if not embedding_base_url:
        errors.append("EMBEDDING_BASE_URL is missing")

    if not embedding_model:
        errors.append("EMBEDDING_MODEL is missing")

    if not PROBE_OUTPUT_FILE.exists():
        errors.append("embedding_probe_result.json is missing")

    if probe_result.get("status") != "passed":
        errors.append(
            "embedding probe has not passed; run "
            "scripts/probe_real_embedding_dimension.py after configuring service"
        )

    vector_dimension = probe_result.get("vector_dimension")

    if not isinstance(vector_dimension, int) or vector_dimension <= 0:
        errors.append("probe vector_dimension is missing or invalid")

    if embedding_dimension_text:
        try:
            env_dimension = int(embedding_dimension_text)
        except ValueError:
            errors.append("EMBEDDING_DIMENSION must be integer")
        else:
            if isinstance(vector_dimension, int) and env_dimension != vector_dimension:
                errors.append(
                    "EMBEDDING_DIMENSION does not match probe vector_dimension: "
                    f"env={env_dimension}, probe={vector_dimension}"
                )
    else:
        warnings.append(
            "EMBEDDING_DIMENSION is empty; it can be filled from probe result "
            "after real probe passes"
        )

    if not qdrant_collection_quality:
        warnings.append(
            "QDRANT_COLLECTION_QUALITY is empty; default target will be "
            f"{QUALITY_COLLECTION_NAME}"
        )
    elif qdrant_collection_quality != QUALITY_COLLECTION_NAME:
        warnings.append(
            "QDRANT_COLLECTION_QUALITY is not quality_kb_v1; confirm before B5"
        )

    result: dict[str, Any] = {
        "env_status": env_status,
        "probe_result": probe_result,
        "quality_collection_target": QUALITY_COLLECTION_NAME,
        "ready_for_b5_create_collection": not errors,
        "errors": errors,
        "warnings": warnings,
    }

    pprint(result)

    if errors:
        print("embedding config gate check failed")
        return False

    print("embedding config gate check passed")
    return True


def load_probe_result() -> dict[str, Any]:
    """Load probe result JSON."""

    if not PROBE_OUTPUT_FILE.exists():
        return {}

    try:
        data = json.loads(PROBE_OUTPUT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "invalid_json",
        }

    if not isinstance(data, dict):
        return {
            "status": "invalid_payload",
        }

    return {
        str(key): value
        for key, value in data.items()
    }


def main() -> int:
    """Run check."""

    passed = check_embedding_config_gate()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())