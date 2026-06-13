# ruff: noqa: E402,I001
"""Check Qdrant connection.

This script verifies Qdrant REST connection.

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

from app.agent.rag import DEFAULT_QDRANT_URL, QdrantStoreError, QdrantVectorStore


def main() -> int:
    """Run Qdrant connection check."""

    print("=" * 80)
    print("checking Qdrant connection")
    print(f"qdrant_url: {DEFAULT_QDRANT_URL}")

    store = QdrantVectorStore(
        base_url=DEFAULT_QDRANT_URL,
        timeout=5.0,
    )

    try:
        collections = store.list_collections()
    except QdrantStoreError as exc:
        print("qdrant connection check failed")
        print(str(exc))
        return 1

    pprint(
        {
            "qdrant_url": DEFAULT_QDRANT_URL,
            "collections": collections,
            "collection_count": len(collections),
        }
    )

    print("qdrant connection check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())