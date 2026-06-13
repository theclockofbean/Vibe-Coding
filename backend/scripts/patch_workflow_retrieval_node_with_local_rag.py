"""Patch LangGraph RetrievalNode with LocalRetriever + EvidenceFilter."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")

if "from sqlalchemy.orm import Session" not in content:
    anchor = "from langgraph.graph import END, START, StateGraph\n"
    content = content.replace(
        anchor,
        anchor + "from sqlalchemy.orm import Session\n",
    )

if "from app.agent.rag import (" not in content:
    anchor = "from app.agent.services import"
    rag_import = """from app.agent.rag import (
    LocalKnowledgeChunkRetriever,
    NullRetriever,
    filter_retrieved_chunk_dicts,
)
"""
    content = content.replace(anchor, rag_import + anchor)

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
        selected_module = _optional_state_str(new_state.get("selected_module"))
        matched_sku = _optional_state_str(new_state.get("matched_sku"))

        if not user_text:
            apply_retrieved_chunks(new_state, [])

            metadata["retrieval_mode"] = "skipped_empty_query"
            metadata["retrieved_chunk_count"] = 0
            metadata["retrieval_rejected_count"] = 0
            metadata["retrieval_warning_count"] = 0

            return new_state

        repository_session = _get_repository_session(self.product_repository)

        if repository_session is None:
            retriever = NullRetriever(reason="repository_session_unavailable")
            raw_chunks = retriever.retrieve(
                query=user_text,
                selected_module=selected_module,
                matched_sku=matched_sku,
                top_k=5,
            )
            retrieval_mode = "null"
        else:
            retriever = LocalKnowledgeChunkRetriever(
                session=repository_session,
                score_threshold=0.01,
                max_candidates=50,
            )
            raw_chunks = retriever.retrieve(
                query=user_text,
                selected_module=selected_module,
                matched_sku=matched_sku,
                top_k=5,
            )
            retrieval_mode = "local_postgres"

        filtered_result = filter_retrieved_chunk_dicts(
            chunks=raw_chunks,
            selected_module=selected_module,
            commitment_context=False,
            score_threshold=0.01,
        )

        safe_chunk_dicts = filtered_result.to_retrieved_chunk_dicts()

        apply_retrieved_chunks(
            new_state,
            safe_chunk_dicts,
        )

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
        metadata["retrieval_selected_module"] = selected_module
        metadata["retrieval_matched_sku"] = matched_sku
        metadata["retrieval_filter"] = filtered_result.metadata

        return new_state

'''

content = content[:start] + replacement + content[end:]

helpers = '''

def _optional_state_str(
    value: object,
) -> str | None:
    """Return stripped text or None."""

    if value is None:
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    return text_value


def _get_repository_session(
    repository: object,
) -> Session | None:
    """Extract SQLAlchemy Session from a repository if available."""

    session = getattr(repository, "session", None)

    if isinstance(session, Session):
        return session

    return None


def _merge_source_references(
    *,
    existing_value: object,
    new_references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge source references without duplicating RAG chunk references."""

    merged: list[dict[str, Any]] = []

    if isinstance(existing_value, list):
        for item in existing_value:
            if isinstance(item, dict):
                merged.append(
                    {
                        str(key): value
                        for key, value in item.items()
                    }
                )

    existing_keys = {
        _source_reference_key(reference)
        for reference in merged
    }

    for reference in new_references:
        normalized_reference = {
            str(key): value
            for key, value in reference.items()
        }
        reference_key = _source_reference_key(normalized_reference)

        if reference_key in existing_keys:
            continue

        merged.append(normalized_reference)
        existing_keys.add(reference_key)

    return merged


def _source_reference_key(
    reference: dict[str, Any],
) -> str:
    """Return stable source reference key."""

    return "|".join(
        [
            str(reference.get("source_type") or ""),
            str(reference.get("collection") or ""),
            str(reference.get("reference_id") or ""),
            str(reference.get("module") or ""),
        ]
    )


def _as_text_list(
    value: object,
) -> list[str]:
    """Return list[str] from unknown value."""

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
        if str(item).strip()
    ]


def _deduplicate_text_list(
    values: list[str],
) -> list[str]:
    """Deduplicate text list while preserving order."""

    result: list[str] = []

    for value in values:
        if value not in result:
            result.append(value)

    return result

'''

if "def _optional_state_str(" not in content:
    anchor = "\ndef _deterministic_pre_route("
    content = content.replace(anchor, helpers + anchor)

target.write_text(content, encoding="utf-8")

print("patched workflow retrieval node with local RAG")