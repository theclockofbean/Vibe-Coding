"""Create and verify Qdrant collection for real Logistics KB."""

from __future__ import annotations

import json
import os
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import httpx


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "logistics_kb_v1"
DEFAULT_VECTOR_SIZE: Final[int] = 1024
DEFAULT_DISTANCE: Final[str] = "Cosine"


def create_logistics_qdrant_collection() -> bool:
    """Create and verify logistics_kb_v1 collection."""

    print("=" * 80)
    print("creating/verifying logistics Qdrant collection")

    load_env_file(ENV_FILE)

    qdrant_url = get_qdrant_url()
    collection_name = os.getenv(
        "QDRANT_COLLECTION_LOGISTICS",
        DEFAULT_COLLECTION_NAME,
    ).strip() or DEFAULT_COLLECTION_NAME
    vector_size = get_int_env("EMBEDDING_DIMENSION", DEFAULT_VECTOR_SIZE)

    errors: list[str] = []
    created = False

    with httpx.Client(timeout=30.0) as client:
        existing = get_collection(
            client=client,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
        )

        if existing is None:
            create_collection(
                client=client,
                qdrant_url=qdrant_url,
                collection_name=collection_name,
                vector_size=vector_size,
            )
            created = True

        collection_info = get_collection(
            client=client,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
        )

    if collection_info is None:
        errors.append(f"collection not found after create: {collection_name}")
        result = {
            "qdrant_url": qdrant_url,
            "collection_name": collection_name,
            "created": created,
            "verified": False,
            "errors": errors,
        }
        pprint(result)
        print("logistics Qdrant collection check failed")
        return False

    vectors_config = extract_vectors_config(collection_info)
    actual_size = vectors_config.get("size")
    actual_distance = vectors_config.get("distance")
    points_count = collection_info.get("points_count")
    status = collection_info.get("status")

    if actual_size != vector_size:
        errors.append(
            f"vector size must be {vector_size}, got {actual_size}"
        )

    if str(actual_distance).lower() != DEFAULT_DISTANCE.lower():
        errors.append(
            f"distance must be {DEFAULT_DISTANCE}, got {actual_distance}"
        )

    result = {
        "qdrant_url": qdrant_url,
        "collection_name": collection_name,
        "created": created,
        "verified": not errors,
        "collection_status": status,
        "vector_size": actual_size,
        "expected_vector_size": vector_size,
        "distance": actual_distance,
        "points_count": points_count,
        "errors": errors,
    }

    output_file = (
        PROJECT_ROOT
        / "data"
        / "parsed"
        / "logistics"
        / "logistics_qdrant_collection_check_result.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pprint(result)

    if errors:
        print("logistics Qdrant collection check failed")
        return False

    print("logistics Qdrant collection check passed")
    return True


def get_collection(
    *,
    client: httpx.Client,
    qdrant_url: str,
    collection_name: str,
) -> dict[str, Any] | None:
    """Get Qdrant collection info."""

    response = client.get(f"{qdrant_url}/collections/{collection_name}")

    if response.status_code == 404:
        return None

    response.raise_for_status()
    payload = response.json()
    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected Qdrant collection response: {payload}")

    return result


def create_collection(
    *,
    client: httpx.Client,
    qdrant_url: str,
    collection_name: str,
    vector_size: int,
) -> None:
    """Create Qdrant collection."""

    payload = {
        "vectors": {
            "size": vector_size,
            "distance": DEFAULT_DISTANCE,
        },
    }

    response = client.put(
        f"{qdrant_url}/collections/{collection_name}",
        json=payload,
    )
    response.raise_for_status()


def extract_vectors_config(
    collection_info: dict[str, Any],
) -> dict[str, Any]:
    """Extract vectors config from Qdrant collection info."""

    config = collection_info.get("config")

    if not isinstance(config, dict):
        return {}

    params = config.get("params")

    if not isinstance(params, dict):
        return {}

    vectors = params.get("vectors")

    if isinstance(vectors, dict):
        return vectors

    return {}


def get_qdrant_url() -> str:
    """Build Qdrant URL from env."""

    explicit_url = os.getenv("QDRANT_URL", "").strip()

    if explicit_url:
        return explicit_url.rstrip("/")

    host = os.getenv("QDRANT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.getenv("QDRANT_PORT", "6333").strip() or "6333"

    return f"http://{host}:{port}"


def get_int_env(
    key: str,
    default: int,
) -> int:
    """Read integer env."""

    value = os.getenv(key, "").strip()

    if not value:
        return default

    return int(value)


def load_env_file(
    env_file: Path,
) -> None:
    """Load simple KEY=VALUE env file without overriding existing env."""

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    """Run script."""

    passed = create_logistics_qdrant_collection()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())