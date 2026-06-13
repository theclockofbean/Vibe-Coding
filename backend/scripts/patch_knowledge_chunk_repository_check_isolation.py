"""Patch KnowledgeChunkRepository check to isolate its own test rows."""

from __future__ import annotations

from pathlib import Path


def replace_function(
    *,
    content: str,
    function_name: str,
    next_function_name: str,
    replacement: str,
) -> str:
    """Replace one top-level function."""

    start = content.index(f"def {function_name}(")
    end = content.index(f"\ndef {next_function_name}(", start)

    return content[:start] + replacement + content[end:]


target = Path("scripts/check_knowledge_chunk_repository.py")
content = target.read_text(encoding="utf-8")

content = replace_function(
    content=content,
    function_name="check_list_for_retrieval",
    next_function_name="check_mark_qdrant_point",
    replacement='''def check_list_for_retrieval() -> bool:
    """Check retrieval filtering query."""

    print("=" * 80)
    print("checking list_for_retrieval")

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = KnowledgeChunkRepository(session)

        quality_sku001_rows = repository.list_for_retrieval(
            selected_module="quality",
            matched_sku="SKU001",
            limit=50,
        )
        quality_sku999_rows = repository.list_for_retrieval(
            selected_module="quality",
            matched_sku="SKU999",
            limit=50,
        )
        quality_count = repository.count_for_retrieval(
            selected_module="quality",
            matched_sku="SKU001",
        )

    quality_sku001_test_rows = [
        row
        for row in quality_sku001_rows
        if row["source_name"] == TEST_SOURCE_NAME
    ]
    quality_sku999_test_rows = [
        row
        for row in quality_sku999_rows
        if row["source_name"] == TEST_SOURCE_NAME
    ]

    quality_sku001_ids = {
        str(row["chunk_id"])
        for row in quality_sku001_test_rows
    }
    quality_sku999_ids = {
        str(row["chunk_id"])
        for row in quality_sku999_test_rows
    }

    pprint(
        {
            "all_quality_sku001_count": len(quality_sku001_rows),
            "all_quality_sku999_count": len(quality_sku999_rows),
            "repository_quality_sku001": sorted(quality_sku001_ids),
            "repository_quality_sku999": sorted(quality_sku999_ids),
            "quality_count": quality_count,
        }
    )

    checks = [
        quality_count >= 2,
        quality_sku001_ids == {
            "repo_quality_sku001",
            "repo_general_boundary",
        },
        quality_sku999_ids == {
            "repo_general_boundary",
        },
        "repo_inactive_quality" not in quality_sku001_ids,
        "repo_no_answer_reference" not in quality_sku001_ids,
        "repo_price_mismatch" not in quality_sku001_ids,
    ]

    return all(checks)

''',
)

content = replace_function(
    content=content,
    function_name="check_set_active",
    next_function_name="check_not_found_cases",
    replacement='''def check_set_active() -> bool:
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
            limit=50,
        )

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)
            active_row = repository.set_active(
                chunk_id="repo_quality_sku001",
                is_active=True,
            )

    test_rows_after_inactive = [
        row
        for row in rows_after_inactive
        if row["source_name"] == TEST_SOURCE_NAME
    ]

    ids_after_inactive = {
        str(row["chunk_id"])
        for row in test_rows_after_inactive
    }

    pprint(inactive_row)
    pprint(test_rows_after_inactive)
    pprint(active_row)

    checks = [
        inactive_row is not None,
        inactive_row is not None and inactive_row["is_active"] is False,
        ids_after_inactive == {"repo_general_boundary"},
        active_row is not None,
        active_row is not None and active_row["is_active"] is True,
    ]

    return all(checks)

''',
)

content = replace_function(
    content=content,
    function_name="check_no_forbidden_commitments",
    next_function_name="main",
    replacement='''def check_no_forbidden_commitments() -> bool:
    """Check repository rows keep commitment reference disabled by default."""

    print("=" * 80)
    print("checking no forbidden commitments")

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = KnowledgeChunkRepository(session)
        rows = repository.list_for_retrieval(
            selected_module="quality",
            matched_sku="SKU001",
            limit=50,
        )

    test_rows = [
        row
        for row in rows
        if row["source_name"] == TEST_SOURCE_NAME
    ]

    serialized_rows = str(test_rows)

    forbidden_fragments = [
        "保证最低价",
        "最低价给你",
        "一定包邮",
        "保证到货",
        "今天一定发",
        "保证不坏",
        "保证不生锈",
        "保证不掉漆",
        "保证耐用",
        "能用几年",
        "一年质保",
        "终身质保",
        "七天无理由",
        "一定能退",
        "一定能换",
        "一定赔",
        "一定补发",
        "质量很好",
        "放心用",
        "完全没问题",
    ]

    checks = [
        all(row["allow_commitment_reference"] is False for row in test_rows),
        all(fragment not in serialized_rows for fragment in forbidden_fragments),
    ]

    return all(checks)

''',
)

target.write_text(content, encoding="utf-8")

print("patched check_knowledge_chunk_repository.py isolation")