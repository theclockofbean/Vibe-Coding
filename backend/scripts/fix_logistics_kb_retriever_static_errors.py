"""Fix static errors in LogisticsKBQdrantRetriever adapter files."""

from __future__ import annotations

from pathlib import Path

RETRIEVER_FILE = Path("app/agent/rag/logistics_kb_retriever.py")
RAG_INIT_FILE = Path("app/agent/rag/__init__.py")


def fix_retriever_file() -> None:
    """Fix logistics retriever static errors."""

    content = RETRIEVER_FILE.read_text(encoding="utf-8")

    content = content.replace(
        '''            "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
''',
        '''            "metadata": (
                payload.get("metadata")
                if isinstance(payload.get("metadata"), dict)
                else {}
            ),
''',
        1,
    )

    content = content.replace(
        '''        query_vector = self._embedding_client.embed_one(cleaned_query)
        limit = top_k if top_k is not None else self._top_k
''',
        '''        query_vectors = self._embedding_client.embed_texts([cleaned_query])

        if not query_vectors:
            raise RuntimeError("embedding client returned empty vector list")

        query_vector = query_vectors[0]
        limit = top_k if top_k is not None else self._top_k
''',
        1,
    )

    RETRIEVER_FILE.write_text(content, encoding="utf-8")


def fix_rag_init_file() -> None:
    """Export logistics retriever classes from rag package."""

    content = RAG_INIT_FILE.read_text(encoding="utf-8")

    old_import = '''from app.agent.rag.logistics_kb_retriever import (
    LogisticsKBHit,
    LogisticsKBQdrantRetriever,
)
'''

    new_import = '''from .logistics_kb_retriever import LogisticsKBHit as LogisticsKBHit
from .logistics_kb_retriever import (
    LogisticsKBQdrantRetriever as LogisticsKBQdrantRetriever,
)
'''

    if old_import in content:
        content = content.replace(old_import, new_import, 1)

    if '"LogisticsKBHit",' not in content and '"validate_embedding_vector",' in content:
        content = content.replace(
            '''    "validate_embedding_vector",
]''',
            '''    "validate_embedding_vector",
    "LogisticsKBHit",
    "LogisticsKBQdrantRetriever",
]''',
            1,
        )

    RAG_INIT_FILE.write_text(content, encoding="utf-8")


def main() -> int:
    """Run fixes."""

    fix_retriever_file()
    fix_rag_init_file()

    print("logistics retriever static errors fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())