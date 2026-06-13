# ruff: noqa: E402,I001
"""Check KnowledgeChunkRepository.

This script verifies PostgreSQL metadata repository behavior for RAG chunks.

It does not call Qdrant, call an LLM, generate embeddings, generate answers,
promise prices, promise logistics, promise quality, promise warranty, promise
returns/exchanges, or create business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import KnowledgeChunk
from app.core.database import get_session_factory
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository


TEST_SOURCE_NAME: Final[str] = "repository_check_source"


def cleanup_test_rows() -> None:
    """Delete repository check rows."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM knowledge_chunks
                    WHERE source_name = :source_name;
                    """
                ),
                {
                    "source_name": TEST_SOURCE_NAME,
                },
            )


def build_chunks() -> list[KnowledgeChunk]:
    """Build deterministic test chunks."""

    return [
        KnowledgeChunk(
            chunk_id="repo_quality_sku001",
            source_type="manual_doc",
            source_name=TEST_SOURCE_NAME,
            doc_id="quality_doc",
            doc_title="质量边界说明",
            chunk_index=0,
            module="quality",
            sku_scope=["SKU001"],
            intent_scope=["material_explanation"],
            content=(
                "铝合金 6061 是常见轻量化材料；具体质量结论必须以"
                "正式规则或人工确认为准。"
            ),
            summary="SKU001 材料说明边界。",
            risk_level="medium",
            is_verified=True,
            allow_answer_reference=True,
        ),
        KnowledgeChunk(
            chunk_id="repo_general_boundary",
            source_type="manual_doc",
            source_name=TEST_SOURCE_NAME,
            doc_id="general_boundary_doc",
            doc_title="RAG 使用边界",
            chunk_index=0,
            module="general",
            content="RAG 只作为补充说明来源，不作为业务承诺来源。",
            summary="RAG 使用边界。",
            risk_level="low",
            is_verified=False,
            allow_answer_reference=True,
        ),
        KnowledgeChunk(
            chunk_id="repo_inactive_quality",
            source_type="manual_doc",
            source_name=TEST_SOURCE_NAME,
            doc_id="inactive_doc",
            doc_title="Inactive Chunk",
            chunk_index=0,
            module="quality",
            content="inactive chunk should not be retrieved",
            is_active=False,
            is_verified=True,
            allow_answer_reference=True,
        ),
        KnowledgeChunk(
            chunk_id="repo_no_answer_reference",
            source_type="manual_doc",
            source_name=TEST_SOURCE_NAME,
            doc_id="no_answer_doc",
            doc_title="No Answer Reference",
            chunk_index=0,
            module="quality",
            content="answer reference disabled chunk should not be retrieved",
            is_verified=True,
            allow_answer_reference=False,
        ),
        KnowledgeChunk(
            chunk_id="repo_price_mismatch",
            source_type="manual_doc",
            source_name=TEST_SOURCE_NAME,
            doc_id="price_doc",
            doc_title="Price Boundary",
            chunk_index=0,
            module="price",
            content="报价必须以正式价格表或人工确认为准。",
            is_verified=True,
            allow_answer_reference=True,
        ),
    ]


def seed_chunks() -> None:
    """Seed chunks through repository."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)

            for chunk in build_chunks():
                repository.upsert_chunk(chunk)


def check_upsert_and_get() -> bool:
    """Check upsert and get behavior."""

    print("=" * 80)
    print("checking upsert and get")

    cleanup_test_rows()
    seed_chunks()

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = KnowledgeChunkRepository(session)

        row = repository.get_by_chunk_id("repo_quality_sku001")

    pprint(row)

    checks = [
        row is not None,
        row is not None and row["chunk_id"] == "repo_quality_sku001",
        row is not None and row["collection_name"] == "kb_chunks_v1",
        row is not None and row["module"] == "quality",
        row is not None and row["sku_scope"] == ["SKU001"],
        row is not None and row["intent_scope"] == ["material_explanation"],
        row is not None and row["risk_level"] == "medium",
        row is not None and row["is_verified"] is True,
        row is not None and row["allow_answer_reference"] is True,
        row is not None and row["allow_commitment_reference"] is False,
    ]

    return all(checks)


def check_upsert_updates_existing_row() -> bool:
    """Check upsert updates existing row."""

    print("=" * 80)
    print("checking upsert updates existing row")

    updated_chunk = KnowledgeChunk(
        chunk_id="repo_quality_sku001",
        source_type="manual_doc",
        source_name=TEST_SOURCE_NAME,
        doc_id="quality_doc",
        doc_title="质量边界说明",
        chunk_index=0,
        module="quality",
        sku_scope=["SKU001"],
        intent_scope=["material_explanation"],
        content=(
            "铝合金 6061 是常见轻量化材料；具体质量结论必须以"
            "正式规则或人工确认为准。"
        ),
        summary="已更新的 SKU001 材料说明边界。",
        risk_level="medium",
        is_verified=True,
        allow_answer_reference=True,
    )

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)
            updated_row = repository.upsert_chunk(updated_chunk)

    pprint(updated_row)

    checks = [
        updated_row["chunk_id"] == "repo_quality_sku001",
        updated_row["summary"] == "已更新的 SKU001 材料说明边界。",
    ]

    return all(checks)


def check_list_for_retrieval() -> bool:
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


def check_mark_qdrant_point() -> bool:
    """Check Qdrant point metadata update."""

    print("=" * 80)
    print("checking mark_qdrant_point")

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)
            row = repository.mark_qdrant_point(
                chunk_id="repo_quality_sku001",
                collection_name="kb_chunks_v1",
                qdrant_point_id="point-repo-quality-sku001",
                embedding_model="test-embedding",
                embedding_dimension=8,
            )

    pprint(row)

    checks = [
        row is not None,
        row is not None and row["qdrant_point_id"] == "point-repo-quality-sku001",
        row is not None and row["embedding_model"] == "test-embedding",
        row is not None and row["embedding_dimension"] == 8,
    ]

    return all(checks)


def check_set_active() -> bool:
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


def check_not_found_cases() -> bool:
    """Check not-found behavior."""

    print("=" * 80)
    print("checking not found cases")

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)
            missing_get = repository.get_by_chunk_id("missing_chunk")
            missing_point = repository.mark_qdrant_point(
                chunk_id="missing_chunk",
                collection_name="kb_chunks_v1",
                qdrant_point_id="missing-point",
                embedding_model="test-embedding",
                embedding_dimension=8,
            )
            missing_active = repository.set_active(
                chunk_id="missing_chunk",
                is_active=False,
            )

    checks = [
        missing_get is None,
        missing_point is None,
        missing_active is None,
    ]

    return all(checks)


def check_no_forbidden_commitments() -> bool:
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


def main() -> int:
    """Run KnowledgeChunkRepository checks."""

    cleanup_test_rows()

    try:
        results = [
            check_upsert_and_get(),
            check_upsert_updates_existing_row(),
            check_list_for_retrieval(),
            check_mark_qdrant_point(),
            check_set_active(),
            check_not_found_cases(),
            check_no_forbidden_commitments(),
        ]
    finally:
        cleanup_test_rows()

    print("=" * 80)

    if not all(results):
        print("knowledge chunk repository check failed")
        return 1

    print("knowledge chunk repository check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())