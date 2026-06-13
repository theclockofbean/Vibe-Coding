"""Fix Logistics Qdrant upsert query collection column and cursor typing."""

from __future__ import annotations

from pathlib import Path

UPSERT_FILE = Path("scripts/upsert_logistics_kb_chunks_to_qdrant.py")


def main() -> int:
    """Patch query and cursor.description typing."""

    content = UPSERT_FILE.read_text(encoding="utf-8")

    content = content.replace(
        "          AND qdrant_collection_name = 'logistics_kb_v1'\n",
        "          AND collection_name = 'logistics_kb_v1'\n",
        1,
    )

    old = '''        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [description.name for description in cursor.description]
'''

    new = '''        cursor.execute(query)
        rows = cursor.fetchall()
        assert cursor.description is not None
        column_names = [description.name for description in cursor.description]
'''

    if old in content:
        content = content.replace(old, new, 1)

    UPSERT_FILE.write_text(content, encoding="utf-8")

    print("logistics Qdrant upsert query collection column fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())