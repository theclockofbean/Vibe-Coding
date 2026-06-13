# ruff: noqa: E402,I001
"""Check Workflow integration with real Price KB retriever."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import AgentState
from app.agent.workflow import build_agent_workflow
from app.core.database import get_session_factory
from app.repositories import ProductRepository


QUERY: Final[str] = "SKU001多少钱？"
EXPECTED_COLLECTION_NAME: Final[str] = "price_kb_v1"


def main() -> int:
    """Run Workflow Price KB integration check."""

    print("=" * 80)
    print("checking workflow real Price KB retrieval integration")

    set_required_env()

    errors: list[str] = []

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session=session)
        workflow = build_agent_workflow(
            product_repository=product_repository,
            conversation_repository=None,
        )

        initial_state = cast(
            AgentState,
            {
                "user_text": QUERY,
                "current_message": QUERY,
                "user_message": QUERY,
                "query": QUERY,
                "intent": "price",
                "selected_module": "price",
                "candidate_modules": ["price"],
                "metadata": {
                    "test_case": "workflow_price_kb_integration",
                },
            },
        )

        result_state = workflow.invoke(initial_state)

    metadata = ensure_dict(result_state.get("metadata"))
    retrieved_chunks = ensure_list(result_state.get("retrieved_chunks"))
    top_chunk = (
        ensure_dict(retrieved_chunks[0])
        if retrieved_chunks
        else {}
    )

    if metadata.get("real_price_kb_retriever_used") is not True:
        errors.append("real_price_kb_retriever_used must be true")

    if metadata.get("retrieval_source") != "real_price_kb":
        errors.append("retrieval_source must be real_price_kb")

    if metadata.get("retrieval_selected_module") != "price":
        errors.append("retrieval_selected_module must be price")

    if metadata.get("retrieval_collection_name") != EXPECTED_COLLECTION_NAME:
        errors.append("retrieval_collection_name must be price_kb_v1")

    if not retrieved_chunks:
        errors.append("retrieved_chunks is empty")

    if top_chunk:
        if top_chunk.get("collection_name") != EXPECTED_COLLECTION_NAME:
            errors.append("top retrieved chunk collection_name must be price_kb_v1")

        if top_chunk.get("module") != "price":
            errors.append("top retrieved chunk module must be price")

        if top_chunk.get("allow_answer_reference") is not True:
            errors.append("top chunk allow_answer_reference must be true")

        if top_chunk.get("allow_commitment_reference") is not False:
            errors.append("top chunk allow_commitment_reference must be false")

        if not str(top_chunk.get("content", "")).strip():
            errors.append("top retrieved chunk content is empty")

    result: dict[str, Any] = {
        "query": QUERY,
        "intent": result_state.get("intent"),
        "selected_module": result_state.get("selected_module"),
        "metadata": {
            key: metadata.get(key)
            for key in (
                "real_price_kb_retriever_enabled",
                "real_price_kb_retriever_used",
                "real_price_kb_retriever_error",
                "retrieval_source",
                "retrieval_selected_module",
                "retrieval_collection_name",
                "retrieval_hit_count",
            )
        },
        "retrieved_chunk_count": len(retrieved_chunks),
        "top_retrieved_chunk": safe_chunk_preview(top_chunk),
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("workflow real Price KB retrieval integration check failed")
        return 1

    print("workflow real Price KB retrieval integration check passed")
    return 0


def set_required_env() -> None:
    """Set required env vars."""

    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_PRICE"] = EXPECTED_COLLECTION_NAME
    os.environ["PRICE_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"


def ensure_dict(
    value: object,
) -> dict[str, Any]:
    """Return dict value."""

    if isinstance(value, dict):
        return {
            str(key): item_value
            for key, item_value in value.items()
        }

    return {}


def ensure_list(
    value: object,
) -> list[Any]:
    """Return list value."""

    if isinstance(value, list):
        return value

    return []


def safe_chunk_preview(
    chunk: dict[str, Any],
) -> dict[str, Any]:
    """Return safe chunk preview."""

    allowed_keys = {
        "chunk_id",
        "doc_id",
        "doc_title",
        "summary",
        "score",
        "collection_name",
        "module",
        "source_type",
        "source_name",
        "qa_id",
        "intent_subtype",
        "risk_flags",
        "risk_level",
        "allow_answer_reference",
        "allow_commitment_reference",
        "is_verified",
    }

    return {
        key: value
        for key, value in chunk.items()
        if key in allowed_keys
    }


if __name__ == "__main__":
    raise SystemExit(main())