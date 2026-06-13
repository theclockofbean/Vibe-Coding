# ruff: noqa: E402,I001
"""Create quality_kb_v1 Qdrant collection after embedding probe passes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import httpx

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

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "quality_kb_v1"
DEFAULT_DISTANCE: Final[str] = "Cosine"


def create_quality_collection() -> bool:
    """Create or verify quality Qdrant collection."""

    print("=" * 80)
    print("creating/verifying quality Qdrant collection")

    qdrant_url = get_qdrant_url()
    collection_name = (
        os.getenv("QDRANT_COLLECTION_QUALITY", "").strip()
        or DEFAULT_COLLECTION_NAME
    )
    distance = os.getenv("QDRANT_DISTANCE", "").strip() or DEFAULT_DISTANCE
    probe_result = load_probe_result()
    vector_size = get_vector_size_from_probe(probe_result)

    result: dict[str, Any] = {
        "qdrant_url": qdrant_url,
        "collection_name": collection_name,
        "distance": distance,
        "probe_result_status": probe_result.get("status"),
        "vector_size": vector_size,
        "created": False,
        "verified": False,
        "errors": [],
    }

    errors: list[str] = result["errors"]

    if vector_size is None:
        errors.append("valid vector_size not found from embedding probe result")
        pprint(result)
        return False

    if probe_result.get("status") != "passed":
        errors.append("embedding probe result is not passed")
        pprint(result)
        return False

    if probe_result.get("ready_for_quality_collection") is not True:
        errors.append("embedding probe is not ready for quality collection")
        pprint(result)
        return False

    try:
        ensure_qdrant_reachable(qdrant_url)
        existing = get_collection(qdrant_url, collection_name)

        if existing is None:
            create_collection(
                qdrant_url=qdrant_url,
                collection_name=collection_name,
                vector_size=vector_size,
                distance=distance,
            )
            result["created"] = True
            existing = get_collection(qdrant_url, collection_name)

        if existing is None:
            errors.append("collection still missing after create")
            pprint(result)
            return False

        verify_collection_config(
            collection_payload=existing,
            expected_vector_size=vector_size,
            expected_distance=distance,
        )

        result["verified"] = True
        result["collection_status"] = existing.get("status")
        result["points_count"] = existing.get("points_count")
        result["vectors_count"] = existing.get("vectors_count")

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        pprint(result)
        return False

    pprint(result)

    print("quality Qdrant collection check passed")
    return True


def get_qdrant_url() -> str:
    """Build Qdrant URL from env."""

    explicit = os.getenv("QDRANT_URL", "").strip()

    if explicit:
        return explicit.rstrip("/")

    host = os.getenv("QDRANT_HOST", "").strip() or "127.0.0.1"
    port = os.getenv("QDRANT_PORT", "").strip() or "6333"

    return f"http://{host}:{port}".rstrip("/")


def load_probe_result() -> dict[str, Any]:
    """Load embedding probe result."""

    if not PROBE_OUTPUT_FILE.exists():
        return {}

    data = json.loads(PROBE_OUTPUT_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        return {}

    return {
        str(key): value
        for key, value in data.items()
    }


def get_vector_size_from_probe(
    probe_result: dict[str, Any],
) -> int | None:
    """Get vector size from probe result."""

    value = probe_result.get("vector_dimension")

    if isinstance(value, int) and value > 0:
        return value

    return None


def ensure_qdrant_reachable(
    qdrant_url: str,
) -> None:
    """Ensure Qdrant is reachable."""

    response = httpx.get(f"{qdrant_url}/collections", timeout=10.0)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant /collections returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )


def get_collection(
    qdrant_url: str,
    collection_name: str,
) -> dict[str, Any] | None:
    """Get collection payload or None."""

    response = httpx.get(
        f"{qdrant_url}/collections/{collection_name}",
        timeout=10.0,
    )

    if response.status_code == 404:
        return None

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant collection get returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("Qdrant collection response must be JSON object")

    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError("Qdrant collection response missing result object")

    return {
        str(key): value
        for key, value in result.items()
    }


def create_collection(
    *,
    qdrant_url: str,
    collection_name: str,
    vector_size: int,
    distance: str,
) -> None:
    """Create Qdrant collection."""

    payload = {
        "vectors": {
            "size": vector_size,
            "distance": distance,
        }
    }

    response = httpx.put(
        f"{qdrant_url}/collections/{collection_name}",
        json=payload,
        timeout=30.0,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant collection create returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )


def verify_collection_config(
    *,
    collection_payload: dict[str, Any],
    expected_vector_size: int,
    expected_distance: str,
) -> None:
    """Verify collection vector config."""

    vector_config = extract_vector_config(collection_payload)

    actual_size = vector_config.get("size")
    actual_distance = vector_config.get("distance")

    if actual_size != expected_vector_size:
        raise RuntimeError(
            f"collection vector size mismatch: "
            f"expected={expected_vector_size}, actual={actual_size}"
        )

    if str(actual_distance).lower() != expected_distance.lower():
        raise RuntimeError(
            f"collection distance mismatch: "
            f"expected={expected_distance}, actual={actual_distance}"
        )


def extract_vector_config(
    collection_payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract unnamed vector config from Qdrant collection payload."""

    config = collection_payload.get("config")

    if not isinstance(config, dict):
        raise RuntimeError("collection config missing")

    params = config.get("params")

    if not isinstance(params, dict):
        raise RuntimeError("collection config.params missing")

    vectors = params.get("vectors")

    if not isinstance(vectors, dict):
        raise RuntimeError("collection config.params.vectors missing")

    if "size" in vectors and "distance" in vectors:
        return vectors

    raise RuntimeError(
        "named vectors are not expected for quality_kb_v1 in this phase"
    )


def main() -> int:
    """Run collection creation."""

    passed = create_quality_collection()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())