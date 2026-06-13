# ruff: noqa: E402,I001
"""Reset incompatible knowledge_chunks table.

This script drops old/incompatible knowledge_chunks schema so Phase 3-E can
recreate the canonical metadata table.

It does not call an LLM, generate embeddings, call Qdrant, or create business
commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory


def reset_knowledge_chunks_table() -> None:
    """Drop old knowledge_chunks table and trigger function."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DROP TABLE IF EXISTS knowledge_chunks CASCADE;
                    """
                )
            )
            session.execute(
                text(
                    """
                    DROP FUNCTION IF EXISTS set_knowledge_chunks_updated_at()
                    CASCADE;
                    """
                )
            )


def main() -> int:
    """Run reset."""

    reset_knowledge_chunks_table()
    print("knowledge_chunks table reset completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())