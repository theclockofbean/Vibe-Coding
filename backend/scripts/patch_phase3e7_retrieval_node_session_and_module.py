"""Patch RetrievalNode session fallback and RAG module inference."""

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
        """Retrieve RAG evidence chunks through local retriever and filter."""

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

        repository_session = _get_repository_session(self.product_repository)

        if repository_session is not None:
            raw_chunks = _retrieve_local_rag_chunks(
                session=repository_session,
                user_text=user_text,
                selected_module=retrieval_module,
                matched_sku=matched_sku,
            )
            retrieval_mode = "local_postgres"
        else:
            session_factory = get_session_factory()

            with session_factory() as rag_session:
                raw_chunks = _retrieve_local_rag_chunks(
                    session=rag_session,
                    user_text=user_text,
                    selected_module=retrieval_module,
                    matched_sku=matched_sku,
                )

            retrieval_mode = "local_postgres"

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
        metadata["retrieved_chunk_count"] = len(safe_chunk_dicts)
        metadata["retrieval_rejected_count"] = len(filtered_result.rejected_chunks)
        metadata["retrieval_warning_count"] = len(filtered_result.warnings)
        metadata["retrieval_selected_module"] = retrieval_module
        metadata["retrieval_matched_sku"] = matched_sku
        metadata["retrieval_filter"] = filtered_result.metadata

        return new_state

'''

content = content[:start] + replacement + content[end:]

if "def _retrieve_local_rag_chunks(" not in content:
    helper_anchor = "\ndef _optional_state_str("
    helper = '''

def _retrieve_local_rag_chunks(
    *,
    session: Session,
    user_text: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> list[dict[str, Any]]:
    """Retrieve local RAG chunks using PostgreSQL metadata."""

    local_retriever = LocalKnowledgeChunkRetriever(
        session=session,
        score_threshold=0.01,
        max_candidates=50,
    )

    return local_retriever.retrieve(
        query=user_text,
        selected_module=selected_module,
        matched_sku=matched_sku,
        top_k=5,
    )


def _infer_retrieval_module(
    *,
    user_text: str,
    selected_module: str | None,
) -> str | None:
    """Infer retrieval module from text and selected module."""

    normalized_text = user_text.strip().lower()

    price_terms = (
        "多少钱",
        "价格",
        "报价",
        "单价",
        "折扣",
        "采购价",
    )
    logistics_terms = (
        "发货",
        "物流",
        "到货",
        "运费",
        "快递",
        "几天发",
        "几天到",
        "时效",
    )
    quality_terms = (
        "材质",
        "表面处理",
        "阳极氧化",
        "质量",
        "生锈",
        "掉漆",
        "耐用",
        "划痕",
        "氧化",
    )

    if any(term in normalized_text for term in price_terms):
        return "price"

    if any(term in normalized_text for term in logistics_terms):
        return "logistics"

    if any(term in normalized_text for term in quality_terms):
        return "quality"

    return selected_module


def _infer_retrieval_matched_sku(
    *,
    state: AgentState,
    user_text: str,
) -> str | None:
    """Infer matched SKU for retrieval."""

    existing_sku = _optional_state_str(state.get("matched_sku"))

    if existing_sku is not None:
        return existing_sku

    module_payload = state.get("module_payload")

    if isinstance(module_payload, dict):
        for key in (
            "product_reference_value",
            "query_value",
        ):
            value = _optional_state_str(module_payload.get(key))

            if value is not None and value.upper().startswith("SKU"):
                return value.upper()

        sku_ids = module_payload.get("sku_ids")

        if isinstance(sku_ids, list):
            for sku_id in sku_ids:
                value = _optional_state_str(sku_id)

                if value is not None and value.upper().startswith("SKU"):
                    return value.upper()

    return _extract_sku(user_text)

'''
    content = content.replace(helper_anchor, helper + helper_anchor)

target.write_text(content, encoding="utf-8")

print("patched RetrievalNode session fallback and RAG module inference")