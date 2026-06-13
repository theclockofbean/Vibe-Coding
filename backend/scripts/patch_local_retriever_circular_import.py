"""Patch LocalKnowledgeChunkRetriever circular import."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/rag/retriever.py")
content = target.read_text(encoding="utf-8")

content = content.replace(
    "from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository\n",
    "",
)

content = content.replace(
    """        repository = KnowledgeChunkRepository(self.session)
""",
    """        from app.repositories.knowledge_chunk_repository import (
            KnowledgeChunkRepository,
        )

        repository = KnowledgeChunkRepository(self.session)
""",
)

target.write_text(content, encoding="utf-8")

print("patched LocalKnowledgeChunkRetriever circular import")