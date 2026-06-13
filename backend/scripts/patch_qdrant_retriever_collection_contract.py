"""Patch QdrantRetriever output contract for EvidenceFilter."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/rag/qdrant_retriever.py")
content = target.read_text(encoding="utf-8")

old = '''        "chunk_id": _required_text(normalized_payload.get("chunk_id")),
        "collection_name": _required_text(
            normalized_payload.get("collection_name")
        ),
        "source_type": _required_text(normalized_payload.get("source_type")),
'''

new = '''        "chunk_id": _required_text(normalized_payload.get("chunk_id")),
        "collection": _required_text(
            normalized_payload.get("collection_name")
        ),
        "collection_name": _required_text(
            normalized_payload.get("collection_name")
        ),
        "source_type": _required_text(normalized_payload.get("source_type")),
'''

if old not in content:
    raise RuntimeError("target block not found in qdrant_retriever.py")

content = content.replace(old, new)

target.write_text(content, encoding="utf-8")

print("patched QdrantRetriever collection contract")