"""Patch check_set_active transaction boundary."""

from __future__ import annotations

from pathlib import Path


target = Path("scripts/check_knowledge_chunk_repository.py")
content = target.read_text(encoding="utf-8")

start = content.index("def check_set_active() -> bool:")
end = content.index("\ndef check_not_found_cases() -> bool:", start)

replacement = '''def check_set_active() -> bool:
    """Check set_active behavior."""

    print("=" * 80)
    print("checking set_active")

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)
            inactive_row = repository.set_active(
                chunk_id="repo_quality_sku001",
                is_active=False,
            )

    with session_factory() as session:
        repository = KnowledgeChunkRepository(session)
        rows_after_inactive = repository.list_for_retrieval(
            selected_module="quality",
            matched_sku="SKU001",
            limit=20,
        )

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)
            active_row = repository.set_active(
                chunk_id="repo_quality_sku001",
                is_active=True,
            )

    ids_after_inactive = {
        str(row["chunk_id"])
        for row in rows_after_inactive
    }

    pprint(inactive_row)
    pprint(rows_after_inactive)
    pprint(active_row)

    checks = [
        inactive_row is not None,
        inactive_row is not None and inactive_row["is_active"] is False,
        ids_after_inactive == {"repo_general_boundary"},
        active_row is not None,
        active_row is not None and active_row["is_active"] is True,
    ]

    return all(checks)

'''

target.write_text(
    content[:start] + replacement + content[end:],
    encoding="utf-8",
)

print("patched check_set_active")