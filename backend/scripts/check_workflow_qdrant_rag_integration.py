# ruff: noqa: E402,I001
"""Check workflow integration with QdrantRetriever.

This script verifies RetrievalNode prefers QdrantRetriever and falls back to
LocalKnowledgeChunkRetriever when Qdrant is unavailable.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import AgentState
from app.agent.workflow import run_agent_workflow
from app.core.database import get_session_factory
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.product_repository import ProductRepository
from scripts.create_qdrant_collection import main as create_qdrant_collection_main
from scripts.seed_rag_knowledge_chunks import cleanup_existing_seed_rows, seed_chunks
from scripts.upsert_seed_chunks_to_qdrant import upsert_seed_chunks


FORBIDDEN_COMMITMENT_FRAGMENTS: Final[tuple[str, ...]] = (
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
)


def reset_seed_and_qdrant_points() -> None:
    """Reset seed rows and upsert Qdrant points."""

    cleanup_existing_seed_rows()
    seed_chunks()

    create_result = create_qdrant_collection_main()

    if create_result != 0:
        raise RuntimeError("failed to create qdrant collection")

    upsert_seed_chunks()


def count_conversation_messages(
    *,
    session_id: str,
) -> int:
    """Count conversation messages for session."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM conversation_messages
                WHERE session_id = :session_id;
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    return int(result)


def count_handoff_tickets(
    *,
    session_id: str,
) -> int:
    """Count handoff tickets for session."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM handoff_tickets
                WHERE session_id = :session_id;
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    return int(result)


def run_workflow_case(
    *,
    session_id: str,
    user_text: str,
) -> AgentState:
    """Run workflow case."""

    initial_state: AgentState = {
        "session_id": session_id,
        "channel": "workflow_qdrant_rag_check",
        "user_id": "workflow-qdrant-rag-check-user",
        "user_text": user_text,
    }

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        conversation_repository = ConversationRepository(session)

        result_state = run_agent_workflow(
            initial_state=initial_state,
            product_repository=product_repository,
            conversation_repository=conversation_repository,
            limit=5,
        )

    return result_state


def check_qdrant_quality_workflow() -> bool:
    """Check quality workflow uses Qdrant."""

    print("=" * 80)
    print("checking workflow qdrant quality retrieval")

    os.environ.pop("QDRANT_URL", None)

    session_id = "workflow-qdrant-quality-session"

    before_message_count = count_conversation_messages(session_id=session_id)
    before_ticket_count = count_handoff_tickets(session_id=session_id)

    state = run_workflow_case(
        session_id=session_id,
        user_text="SKU001 阳极氧化 表面处理 材质说明",
    )

    after_message_count = count_conversation_messages(session_id=session_id)
    after_ticket_count = count_handoff_tickets(session_id=session_id)

    metadata = _dict_value(state.get("metadata"))
    chunks = _list_of_dicts(state.get("retrieved_chunks"))
    references = _list_of_dicts(state.get("source_references"))

    chunk_ids = {
        str(chunk.get("chunk_id"))
        for chunk in chunks
    }
    rag_reference_ids = {
        str(reference.get("reference_id"))
        for reference in references
        if reference.get("source_type") == "rag_chunk"
    }

    pprint(state)

    checks = [
        metadata.get("retrieval_mode") == "qdrant",
        metadata.get("retrieval_fallback_reason") is None,
        metadata.get("retrieved_chunk_count", 0) >= 2,
        "seed_quality_material_6061" in chunk_ids,
        "seed_quality_anodized_surface" in chunk_ids,
        "seed_quality_material_6061" in rag_reference_ids,
        "seed_quality_anodized_surface" in rag_reference_ids,
        before_message_count == after_message_count,
        before_ticket_count == after_ticket_count,
    ]

    return all(checks)


def check_qdrant_price_workflow() -> bool:
    """Check price workflow uses Qdrant."""

    print("=" * 80)
    print("checking workflow qdrant price retrieval")

    os.environ.pop("QDRANT_URL", None)

    state = run_workflow_case(
        session_id="workflow-qdrant-price-session",
        user_text="SKU001 多少钱 报价 价格边界",
    )

    metadata = _dict_value(state.get("metadata"))
    chunks = _list_of_dicts(state.get("retrieved_chunks"))
    chunk_ids = {
        str(chunk.get("chunk_id"))
        for chunk in chunks
    }

    pprint(state)

    checks = [
        metadata.get("retrieval_mode") == "qdrant",
        "seed_price_boundary" in chunk_ids,
        "seed_quality_material_6061" not in chunk_ids,
        all(chunk.get("allow_commitment_reference") is False for chunk in chunks),
    ]

    return all(checks)


def check_qdrant_logistics_workflow() -> bool:
    """Check logistics workflow uses Qdrant."""

    print("=" * 80)
    print("checking workflow qdrant logistics retrieval")

    os.environ.pop("QDRANT_URL", None)

    state = run_workflow_case(
        session_id="workflow-qdrant-logistics-session",
        user_text="SKU001 发货 物流 到货 时效边界",
    )

    metadata = _dict_value(state.get("metadata"))
    chunks = _list_of_dicts(state.get("retrieved_chunks"))
    chunk_ids = {
        str(chunk.get("chunk_id"))
        for chunk in chunks
    }

    pprint(state)

    checks = [
        metadata.get("retrieval_mode") == "qdrant",
        "seed_logistics_boundary" in chunk_ids,
        "seed_price_boundary" not in chunk_ids,
        all(chunk.get("allow_commitment_reference") is False for chunk in chunks),
    ]

    return all(checks)


def check_qdrant_sku_scope_workflow() -> bool:
    """Check Qdrant workflow SKU scope filtering."""

    print("=" * 80)
    print("checking workflow qdrant SKU scope filtering")

    os.environ.pop("QDRANT_URL", None)

    state = run_workflow_case(
        session_id="workflow-qdrant-sku-scope-session",
        user_text="SKU999 阳极氧化 表面处理 材质说明",
    )

    metadata = _dict_value(state.get("metadata"))
    chunks = _list_of_dicts(state.get("retrieved_chunks"))
    chunk_ids = {
        str(chunk.get("chunk_id"))
        for chunk in chunks
    }

    pprint(state)

    checks = [
        metadata.get("retrieval_mode") == "qdrant",
        "seed_quality_material_6061" not in chunk_ids,
        "seed_quality_anodized_surface" not in chunk_ids,
        "seed_general_rag_boundary" in chunk_ids,
        all(chunk.get("allow_commitment_reference") is False for chunk in chunks),
    ]

    return all(checks)


def check_qdrant_fallback_to_local() -> bool:
    """Check unavailable Qdrant falls back to local PostgreSQL retriever."""

    print("=" * 80)
    print("checking workflow qdrant fallback to local")

    old_qdrant_url = os.environ.get("QDRANT_URL")
    os.environ["QDRANT_URL"] = "http://127.0.0.1:6334"

    try:
        state = run_workflow_case(
            session_id="workflow-qdrant-fallback-session",
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )
    finally:
        if old_qdrant_url is None:
            os.environ.pop("QDRANT_URL", None)
        else:
            os.environ["QDRANT_URL"] = old_qdrant_url

    metadata = _dict_value(state.get("metadata"))
    chunks = _list_of_dicts(state.get("retrieved_chunks"))
    chunk_ids = {
        str(chunk.get("chunk_id"))
        for chunk in chunks
    }

    pprint(state)

    checks = [
        metadata.get("retrieval_mode") == "local_postgres",
        bool(metadata.get("retrieval_fallback_reason")),
        "seed_quality_material_6061" in chunk_ids,
        "seed_quality_anodized_surface" in chunk_ids,
        all(chunk.get("allow_commitment_reference") is False for chunk in chunks),
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check workflow output has no forbidden commitment fragments."""

    print("=" * 80)
    print("checking forbidden commitment fragments")

    os.environ.pop("QDRANT_URL", None)

    state = run_workflow_case(
        session_id="workflow-qdrant-forbidden-session",
        user_text="SKU001 价格 物流 质量 售后 边界",
    )

    serialized = str(state)

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def _dict_value(
    value: object,
) -> dict[str, Any]:
    """Return dict value."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _list_of_dicts(
    value: object,
) -> list[dict[str, Any]]:
    """Return list of dicts."""

    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []

    for item in value:
        if isinstance(item, dict):
            result.append(
                {
                    str(key): item_value
                    for key, item_value in item.items()
                }
            )

    return result


def main() -> int:
    """Run workflow Qdrant RAG integration checks."""

    reset_seed_and_qdrant_points()

    results = [
        check_qdrant_quality_workflow(),
        check_qdrant_price_workflow(),
        check_qdrant_logistics_workflow(),
        check_qdrant_sku_scope_workflow(),
        check_qdrant_fallback_to_local(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("workflow qdrant rag integration check failed")
        return 1

    print("workflow qdrant rag integration check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())