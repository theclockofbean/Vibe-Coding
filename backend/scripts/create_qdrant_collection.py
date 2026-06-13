# ruff: noqa: E402,I001
"""Create Qdrant collection for RAG chunks.

This script creates kb_chunks_v1 collection with deterministic test vector
dimension.

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
    QdrantVectorStore,
)


def main() -> int:
    """Create Qdrant collection."""

    print("=" * 80)
    print("creating Qdrant collection")

    store = QdrantVectorStore(
        base_url=DEFAULT_QDRANT_URL,
        timeout=5.0,
    )

    config = store.ensure_collection(
        collection_name=DEFAULT_QDRANT_COLLECTION,
        vector_size=DEFAULT_QDRANT_VECTOR_SIZE,
        distance=DEFAULT_QDRANT_DISTANCE,
    )

    pprint(config.to_dict())

    print("qdrant collection creation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())