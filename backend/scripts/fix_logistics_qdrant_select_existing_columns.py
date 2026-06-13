"""Fix Logistics Qdrant upsert script to select existing columns only."""

from __future__ import annotations

import re
from pathlib import Path

UPSERT_FILE = Path("scripts/upsert_logistics_kb_chunks_to_qdrant.py")


def main() -> int:
    """Patch fetch_logistics_chunks query to avoid non-existent columns."""

    content = UPSERT_FILE.read_text(encoding="utf-8")

    pattern = re.compile(
        r'    query = """\n'
        r"        SELECT\n"
        r"[\s\S]*?"
        r"        ORDER BY chunk_id\n"
        r'    """',
        re.MULTILINE,
    )

    replacement = '''    query = """
        SELECT *
        FROM knowledge_chunks
        WHERE chunk_id LIKE 'logistics_qa_logi%%'
          AND qdrant_collection_name = 'logistics_kb_v1'
          AND is_active = TRUE
        ORDER BY chunk_id
    """'''

    new_content, count = pattern.subn(replacement, content, count=1)

    if count != 1:
        raise RuntimeError("target SELECT query block not found or replaced more than once")

    UPSERT_FILE.write_text(new_content, encoding="utf-8")

    print("logistics Qdrant upsert SELECT query fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())