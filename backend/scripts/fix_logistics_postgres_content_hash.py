"""Fix Logistics PostgreSQL upsert missing content_hash."""

from __future__ import annotations

from pathlib import Path

UPSERT_FILE = Path("scripts/upsert_logistics_kb_chunks_to_postgres.py")


def main() -> int:
    """Patch build_row_for_chunk to include content_hash."""

    content = UPSERT_FILE.read_text(encoding="utf-8")

    if "import hashlib" not in content:
        content = content.replace("import json\n", "import hashlib\nimport json\n", 1)

    if '"content_hash":' in content:
        print("content_hash already exists in logistics PostgreSQL upsert script")
        UPSERT_FILE.write_text(content, encoding="utf-8")
        return 0

    old = '''        "content": chunk.content,
        "text": chunk.content,
        "summary": chunk.summary,
'''

    new = '''        "content": chunk.content,
        "content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
        "text": chunk.content,
        "summary": chunk.summary,
'''

    if old not in content:
        raise RuntimeError("target content block not found in logistics PostgreSQL upsert script")

    content = content.replace(old, new, 1)
    UPSERT_FILE.write_text(content, encoding="utf-8")

    print("logistics PostgreSQL upsert script content_hash fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())