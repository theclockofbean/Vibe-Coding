"""Create or validate Qdrant collection for Price KB."""

from __future__ import annotations

import os
from pprint import pprint
from typing import Any, Final, cast

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams


COLLECTION_NAME: Final[str] = "price_kb_v1"
VECTOR_SIZE: Final[int] = 1024
DISTANCE: Final[Distance] = Distance.COSINE


def main() -> int:
    """Create or validate Price KB Qdrant collection."""

    print("=" * 80)
    print("creating or validating price_kb_v1 Qdrant collection")

    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    client = QdrantClient(url=qdrant_url)

    errors: list[str] = []

    collection_exists = client.collection_exists(collection_name=COLLECTION_NAME)

    if not collection_exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=DISTANCE,
            ),
        )

    info = client.get_collection(collection_name=COLLECTION_NAME)
    vector_config = get_vector_config(info)

    vector_size = getattr(vector_config, "size", None)
    distance = getattr(vector_config, "distance", None)

    if vector_size != VECTOR_SIZE:
        errors.append(f"vector size must be {VECTOR_SIZE}, got {vector_size}")

    if distance != DISTANCE:
        errors.append(f"distance must be {DISTANCE}, got {distance}")

    result: dict[str, Any] = {
        "qdrant_url": qdrant_url,
        "collection_name": COLLECTION_NAME,
        "collection_existed_before": collection_exists,
        "status": str(info.status),
        "points_count": info.points_count,
        "indexed_vectors_count": getattr(info, "indexed_vectors_count", None),
        "vector_size": vector_size,
        "distance": str(distance),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("price_kb_v1 Qdrant collection check failed")
        return 1

    print("price_kb_v1 Qdrant collection check passed")
    return 0


def get_vector_config(
    info: Any,
) -> Any:
    """Return vector config from Qdrant CollectionInfo."""

    vectors_config = cast(Any, info.config.params.vectors)

    if isinstance(vectors_config, dict):
        if not vectors_config:
            raise ValueError("empty named vectors config")

        return next(iter(vectors_config.values()))

    return vectors_config


if __name__ == "__main__":
    raise SystemExit(main())