# ruff: noqa: E402,I001
"""Check Qdrant collection config.

This script verifies kb_chunks_v1 vector size and distance.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_DISTANCE,
    DEFAULT_QDRANT_URL,
    DEFAULT_QDRANT_VECTOR_SIZE,
    QdrantStoreError,
    QdrantVectorStore,
)


def main() -> int:
    """Check Qdrant collection config."""

    print("=" * 80)
    print("checking Qdrant collection")

    store = QdrantVectorStore(
        base_url=DEFAULT_QDRANT_URL,
        timeout=5.0,
    )

    try:
        config = store.assert_collection_config(
            collection_name=DEFAULT_QDRANT_COLLECTION,
            expected_vector_size=DEFAULT_QDRANT_VECTOR_SIZE,
            expected_distance=DEFAULT_QDRANT_DISTANCE,
        )
    except QdrantStoreError as exc:
        print("qdrant collection check failed")
        print(str(exc))
        return 1

    pprint(config.to_dict())

    checks = [
        config.collection_name == DEFAULT_QDRANT_COLLECTION,
        config.vector_size == DEFAULT_QDRANT_VECTOR_SIZE,
        config.distance.lower() == DEFAULT_QDRANT_DISTANCE.lower(),
    ]

    if not all(checks):
        print("qdrant collection check failed")
        return 1

    print("qdrant collection check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())