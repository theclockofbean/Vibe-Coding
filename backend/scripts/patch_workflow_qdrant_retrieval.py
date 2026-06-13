"""Patch workflow RetrievalNode to prefer QdrantRetriever with local fallback."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")

if "from app.core.database import get_session_factory" not in content:
    content = content.replace(
        "from app.repositories.conversation_repository import ConversationRepository\n",
        "from app.core.database import get_session_factory\n"
        "from app.repositories.conversation_repository import ConversationRepository\n",
    )

start = content.index("    def retrieval_node(")
end = content.index("\n    def risk_control_node(", start)

replacement = '''    def retrieval_node(
        self,
        state: AgentState,
    ) -> AgentState:
        """Retrieve RAG evidence chunks through Qdrant with local fallback."""

        new_state = _copy_state(state)
        metadata = _ensure_metadata(new_state)

        _mark_visited(new_state, "retrieval")

        user_text = str(new_state.get("user_text") or "").strip()
        retrieval_module = _infer_retrieval_module(
            user_text=user_text,
            selected_module=_optional_state_str(new_state.get("selected_module")),
        )
        matched_sku = _infer_retrieval_matched_sku(
            state=new_state,
            user_text=user_text,
        )

        if not user_text:
            new_state["retrieved_chunks"] = []

            metadata["retrieval_mode"] = "skipped_empty_query"
            metadata["retrieved_chunk_count"] = 0
            metadata["retrieval_rejected_count"] = 0
            metadata["retrieval_warning_count"] = 0
            metadata["retrieval_selected_module"] = retrieval_module
            metadata["retrieval_matched_sku"] = matched_sku

            return new_state

        raw_chunks, qdrant_metadata = _retrieve_qdrant_rag_chunks(
            user_text=user_text,
            selected_module=retrieval_module,
            matched_sku=matched_sku,
        )

        retrieval_mode = "qdrant"
        retrieval_fallback_reason: str | None = None

        if not raw_chunks:
            retrieval_mode = "local_postgres"
            retrieval_fallback_reason = str(
                qdrant_metadata.get("fallback_reason")
                or "qdrant_returned_no_chunks"
            )
            raw_chunks = _retrieve_local_rag_chunks_with_session_fallback(
                product_repository=self.product_repository,
                user_text=user_text,
                selected_module=retrieval_module,
                matched_sku=matched_sku,
            )

        filtered_result = filter_retrieved_chunk_dicts(
            chunks=raw_chunks,
            selected_module=retrieval_module,
            commitment_context=False,
            score_threshold=0.01,
        )

        safe_chunk_dicts = filtered_result.to_retrieved_chunk_dicts()

        new_state["retrieved_chunks"] = safe_chunk_dicts

        new_state["source_references"] = _merge_source_references(
            existing_value=new_state.get("source_references"),
            new_references=filtered_result.source_references,
        )

        new_state["warnings"] = _deduplicate_text_list(
            [
                *_as_text_list(new_state.get("warnings")),
                *filtered_result.warnings,
            ]
        )

        new_state["risk_reasons"] = _deduplicate_text_list(
            [
                *_as_text_list(new_state.get("risk_reasons")),
                *filtered_result.risk_reasons,
            ]
        )

        metadata["retrieval_mode"] = retrieval_mode
        metadata["retrieval_fallback_reason"] = retrieval_fallback_reason
        metadata["retrieval_collection_name"] = qdrant_metadata.get(
            "collection_name"
        )
        metadata["retrieval_embedding_model"] = qdrant_metadata.get(
            "embedding_model"
        )
        metadata["retrieval_embedding_dimension"] = qdrant_metadata.get(
            "embedding_dimension"
        )
        metadata["retrieval_qdrant_url"] = qdrant_metadata.get("qdrant_url")
        metadata["retrieved_chunk_count"] = len(safe_chunk_dicts)
        metadata["retrieval_rejected_count"] = len(filtered_result.rejected_chunks)
        metadata["retrieval_warning_count"] = len(filtered_result.warnings)
        metadata["retrieval_selected_module"] = retrieval_module
        metadata["retrieval_matched_sku"] = matched_sku
        metadata["retrieval_filter"] = filtered_result.metadata

        return new_state

'''

content = content[:start] + replacement + content[end:]

if "def _retrieve_qdrant_rag_chunks(" not in content:
    anchor = "\ndef _retrieve_local_rag_chunks("
    helper = '''

def _retrieve_qdrant_rag_chunks(
    *,
    user_text: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retrieve RAG chunks from Qdrant.

    The helper catches Qdrant-layer failures and returns empty chunks plus
    fallback metadata so the workflow can degrade to local PostgreSQL retrieval.
    """

    import os

    from app.agent.rag.embedding import DeterministicHashEmbeddingClient
    from app.agent.rag.qdrant_retriever import QdrantRetriever
    from app.agent.rag.qdrant_store import (
        DEFAULT_QDRANT_COLLECTION,
        DEFAULT_QDRANT_URL,
        DEFAULT_QDRANT_VECTOR_SIZE,
        QdrantStoreError,
        QdrantVectorStore,
    )

    qdrant_url = os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL)
    embedding_model = "deterministic-hash-embedding-v1"

    metadata: dict[str, Any] = {
        "collection_name": DEFAULT_QDRANT_COLLECTION,
        "embedding_model": embedding_model,
        "embedding_dimension": DEFAULT_QDRANT_VECTOR_SIZE,
        "qdrant_url": qdrant_url,
    }

    try:
        vector_store = QdrantVectorStore(
            base_url=qdrant_url,
            timeout=5.0,
        )
        vector_store.assert_collection_config(
            collection_name=DEFAULT_QDRANT_COLLECTION,
            expected_vector_size=DEFAULT_QDRANT_VECTOR_SIZE,
        )

        retriever = QdrantRetriever(
            embedding_client=DeterministicHashEmbeddingClient(
                dimension=DEFAULT_QDRANT_VECTOR_SIZE,
            ),
            vector_store=vector_store,
            collection_name=DEFAULT_QDRANT_COLLECTION,
            embedding_dimension=DEFAULT_QDRANT_VECTOR_SIZE,
            search_limit=50,
        )

        chunks = retriever.retrieve(
            query=user_text,
            selected_module=selected_module,
            matched_sku=matched_sku,
            top_k=5,
        )

        metadata["success"] = True
        metadata["raw_chunk_count"] = len(chunks)

        return chunks, metadata

    except (QdrantStoreError, RuntimeError, ValueError, OSError) as exc:
        metadata["success"] = False
        metadata["fallback_reason"] = f"{type(exc).__name__}: {exc}"

        return [], metadata


def _retrieve_local_rag_chunks_with_session_fallback(
    *,
    product_repository: object,
    user_text: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> list[dict[str, Any]]:
    """Retrieve local chunks using repository session or a temporary session."""

    repository_session = _get_repository_session(product_repository)

    if repository_session is not None:
        return _retrieve_local_rag_chunks(
            session=repository_session,
            user_text=user_text,
            selected_module=selected_module,
            matched_sku=matched_sku,
        )

    session_factory = get_session_factory()

    with session_factory() as rag_session:
        return _retrieve_local_rag_chunks(
            session=rag_session,
            user_text=user_text,
            selected_module=selected_module,
            matched_sku=matched_sku,
        )

'''
    content = content.replace(anchor, helper + anchor)

target.write_text(content, encoding="utf-8")

print("patched workflow RetrievalNode with QdrantRetriever fallback")