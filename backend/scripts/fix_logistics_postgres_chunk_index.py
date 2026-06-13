"""Fix Logistics PostgreSQL upsert missing chunk_index."""

from __future__ import annotations

from pathlib import Path

UPSERT_FILE = Path("scripts/upsert_logistics_kb_chunks_to_postgres.py")


def main() -> int:
    """Patch build_row_for_chunk to include chunk_index."""

    content = UPSERT_FILE.read_text(encoding="utf-8")

    if '"chunk_index":' in content:
        print("chunk_index already exists in logistics PostgreSQL upsert script")
        return 0

    old = '''        "source_row_id": chunk.qa_id,
        "source_row_index": chunk.source_row_index,
        "content": chunk.content,
'''

    new = '''        "source_row_id": chunk.qa_id,
        "source_row_index": chunk.source_row_index,
        "chunk_index": chunk.source_row_index - 2,
        "content": chunk.content,
'''

    if old not in content:
        raise RuntimeError("target block not found in logistics PostgreSQL upsert script")

    content = content.replace(old, new, 1)
    UPSERT_FILE.write_text(content, encoding="utf-8")

    print("logistics PostgreSQL upsert script chunk_index fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())