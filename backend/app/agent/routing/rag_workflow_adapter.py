from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

from app.agent.rag.answer_service import build_default_answer_service
from app.agent.state import AgentState


VALID_WORKFLOW_MODULES = {"spec", "price", "logistics", "quality"}


@dataclass(frozen=True)
class RagWorkflowAdapterConfig:
    min_confidence: float = 0.4
    default_answer_mode: str = "rag_answer_service"


class RagWorkflowAdapter:
    """
    Convert RagAnswerService output into an AgentState-compatible patch.

    This adapter does not run retrieval, embedding, rerank, LLM, or rendering.
    Its only responsibility is schema alignment:

    RagAnswerService.answer()
        -> AgentState patch
        -> existing workflow.py can consume the result safely
    """

    def __init__(self, config: RagWorkflowAdapterConfig | None = None) -> None:
        self.config = config or RagWorkflowAdapterConfig()
        self.answer_service = None   # ✅ 新增这一行

    def adapt_answer_to_state_patch(
        self,
        *,
        rag_result: Mapping[str, Any],
        current_state: Mapping[str, Any] | None = None,
    ) -> AgentState:
        state = current_state or {}

        query = self._text(rag_result.get("query"))
        answer = self._text(rag_result.get("answer"))
        confidence = self._float(rag_result.get("confidence"))
        should_answer = bool(rag_result.get("should_answer", False))

        sources = self._dict_list(rag_result.get("sources"))
        contexts = self._dict_list(rag_result.get("contexts"))

        selected_module = self._select_module(
            rag_result=rag_result,
            sources=sources,
            contexts=contexts,
            current_state=state,
        )

        retrieved_chunks = self._build_retrieved_chunks(contexts)
        source_references = self._build_source_references(sources)

        handoff_required = self._needs_handoff(
            rag_result=rag_result,
            confidence=confidence,
            should_answer=should_answer,
            sources=sources,
            contexts=contexts,
        )

        warnings = self._merge_text_lists(
            state.get("warnings"),
            self._build_warnings(
                should_answer=should_answer,
                confidence=confidence,
                rag_result=rag_result,
            ),
        )

        risk_reasons = self._merge_text_lists(
            state.get("risk_reasons"),
            self._build_risk_reasons(
                rag_result=rag_result,
                sources=sources,
                contexts=contexts,
            ),
        )

        metadata = self._merge_metadata(
            state.get("metadata"),
            {
                "rag_workflow_adapter_used": True,
                "rag_answer_mode": self._metadata_value(
                    rag_result,
                    key="answer_mode",
                    default=self.config.default_answer_mode,
                ),
                "rag_query": query,
                "rag_selected_module": selected_module,
                "rag_should_answer": should_answer,
                "rag_confidence": confidence,
                "rag_source_count": len(sources),
                "rag_context_count": len(contexts),
                "rag_handoff_required": handoff_required,
                "rag_metadata": self._dict_value(rag_result.get("metadata")),
            },
        )

        patch: dict[str, Any] = {
            "selected_module": selected_module,
            "answer_text": rag_result["answer"],
            "retrieved_chunks": retrieved_chunks,
            "source_references": source_references,
            "handoff_required": handoff_required,
            "human_handoff": handoff_required,
            "warnings": warnings,
            "risk_reasons": risk_reasons,
            "metadata": metadata,
        }

        return cast(AgentState, patch)

    def _select_module(
        self,
        *,
        rag_result: Mapping[str, Any],
        sources: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
        current_state: Mapping[str, Any],
    ) -> str | None:
        candidates: list[Any] = [
            rag_result.get("domain"),
            current_state.get("selected_module"),
        ]

        candidates.extend(context.get("domain") for context in contexts)
        candidates.extend(source.get("domain") for source in sources)

        for candidate in candidates:
            module = self._text(candidate)
            if module in VALID_WORKFLOW_MODULES:
                return module

        return None

    def _build_retrieved_chunks(
        self,
        contexts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []

        for index, context in enumerate(contexts, start=1):
            chunks.append(
                {
                    "index": context.get("index", index),
                    "chunk_id": context.get("chunk_id"),
                    "document_id": context.get("document_id"),
                    "domain": context.get("domain"),
                    "source": context.get("source"),
                    "source_type": context.get("source_type"),
                    "text": context.get("text"),
                    "score": context.get("score"),
                    "original_score": context.get("original_score"),
                    "rerank_score": context.get("rerank_score"),
                    "rank": context.get("rank"),
                    "rerank_reason": context.get("rerank_reason"),
                    "metadata": context.get("metadata", {}),
                }
            )

        return chunks

    def _build_source_references(
        self,
        sources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []

        for index, source in enumerate(sources, start=1):
            source_value = source.get("source")
            chunk_id = source.get("chunk_id")
            document_id = source.get("document_id")

            references.append(
                {
                    "index": source.get("index", index),
                    "source_id": chunk_id or document_id or f"rag_source_{index}",
                    "title": source_value or chunk_id or document_id or f"RAG Source {index}",
                    "source": source_value,
                    "source_type": source.get("source_type"),
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "domain": source.get("domain"),
                    "score": source.get("score"),
                    "original_score": source.get("original_score"),
                    "rerank_score": source.get("rerank_score"),
                    "rank": source.get("rank"),
                }
            )

        return references

    def _needs_handoff(
        self,
        *,
        rag_result: Mapping[str, Any],
        confidence: float,
        should_answer: bool,
        sources: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> bool:
        if not should_answer:
            return True

        if confidence < self.config.min_confidence:
            return True

        if bool(rag_result.get("handoff_required")):
            return True

        if self._risk_flags_from_result(rag_result, sources, contexts):
            return True

        return False

    def _build_warnings(
        self,
        *,
        should_answer: bool,
        confidence: float,
        rag_result: Mapping[str, Any],
    ) -> list[str]:
        warnings: list[str] = []

        if not should_answer:
            warnings.append("rag_answer_not_allowed")

        if confidence < self.config.min_confidence:
            warnings.append("rag_low_confidence")

        metadata = self._dict_value(rag_result.get("metadata"))
        refusal_reason = self._text(metadata.get("refusal_reason"))
        if refusal_reason:
            warnings.append(f"rag_refusal_reason:{refusal_reason}")

        return warnings

    def _build_risk_reasons(
        self,
        *,
        rag_result: Mapping[str, Any],
        sources: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> list[str]:
        return self._risk_flags_from_result(rag_result, sources, contexts)

    def _risk_flags_from_result(
        self,
        rag_result: Mapping[str, Any],
        sources: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
    ) -> list[str]:
        flags: list[str] = []

        for value in self._list_value(rag_result.get("risk_flags")):
            text = self._text(value)
            if text:
                flags.append(text)

        for item in [*sources, *contexts]:
            for value in self._list_value(item.get("risk_flags")):
                text = self._text(value)
                if text:
                    flags.append(text)

            metadata = self._dict_value(item.get("metadata"))
            for value in self._list_value(metadata.get("risk_flags")):
                text = self._text(value)
                if text:
                    flags.append(text)

            row = self._dict_value(metadata.get("row"))
            for value in self._list_value(row.get("risk_flags")):
                text = self._text(value)
                if text:
                    flags.append(text)

            if bool(item.get("handoff_required")):
                flags.append("rag_context_handoff_required")

            if bool(metadata.get("handoff_required")):
                flags.append("rag_context_handoff_required")

            if bool(row.get("handoff_required")):
                flags.append("rag_context_handoff_required")

        return sorted(set(flags))

    def _metadata_value(
        self,
        rag_result: Mapping[str, Any],
        *,
        key: str,
        default: Any,
    ) -> Any:
        metadata = self._dict_value(rag_result.get("metadata"))
        return metadata.get(key, default)

    def _merge_metadata(
        self,
        existing: Any,
        update: Mapping[str, Any],
    ) -> dict[str, Any]:
        metadata = self._dict_value(existing)
        metadata.update(dict(update))
        return metadata

    def _merge_text_lists(self, *values: Any) -> list[str]:
        merged: list[str] = []

        for value in values:
            for item in self._list_value(value):
                text = self._text(item)
                if text and text not in merged:
                    merged.append(text)

        return merged

    def _dict_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        result: list[dict[str, Any]] = []

        for item in value:
            if isinstance(item, dict):
                result.append(dict(item))

        return result

    def _dict_value(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _list_value(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, set):
            return list(value)
        if isinstance(value, str):
            if ";" in value:
                return [item.strip() for item in value.split(";") if item.strip()]
            if "," in value:
                return [item.strip() for item in value.split(",") if item.strip()]
            return [value] if value.strip() else []
        return [value]

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _float(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def build_default_rag_workflow_adapter() -> RagWorkflowAdapter:
    return RagWorkflowAdapter()


def apply_rag_answer_to_workflow_state(
    *,
    state: AgentState,
    query: str | None = None,
    domain: str | None = None,
    limit: int = 3,
    score_threshold: float | None = None,
    rerank: bool = True,
    rerank_top_k: int | None = 3,
    adapter: RagWorkflowAdapter | None = None,
) -> AgentState:
    """
    Run RagAnswerService and merge its result into an AgentState-compatible state.

    This is the safe P1-A integration boundary:
    - It does not modify workflow.py node order.
    - It does not replace existing module-specific retrieval.
    - It returns a new state dict with RAG answer fields merged in.
    - It captures errors as metadata + handoff instead of breaking workflow.
    """

    current_state = dict(state)
    metadata = current_state.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    else:
        metadata = dict(metadata)

    effective_query = str(query or current_state.get("user_text") or "").strip()
    effective_domain = str(domain or current_state.get("selected_module") or "").strip() or None

    if not effective_query:
        metadata.update(
            {
                "rag_workflow_integration_used": False,
                "rag_workflow_integration_error": "empty_query",
            }
        )
        current_state["metadata"] = metadata
        current_state["handoff_required"] = True
        current_state["human_handoff"] = True
        current_state["warnings"] = _merge_adapter_text_lists(
            current_state.get("warnings"),
            ["rag_workflow_empty_query"],
        )
        return cast(AgentState, current_state)

    try:
        def _get_answer_service():
            from app.agent.rag.answer_service import build_default_answer_service
            return build_default_answer_service()

        answer_service = (
            adapter.answer_service
            if adapter is not None and hasattr(adapter, "answer_service") and adapter.answer_service is not None
            else build_default_answer_service()
        )
        rag_result = answer_service.answer(
            query=effective_query,
            domain=effective_domain,
            limit=limit,
            score_threshold=score_threshold,
            rerank=rerank,
            rerank_top_k=rerank_top_k,
        )

        effective_adapter = adapter or build_default_rag_workflow_adapter()
        patch = effective_adapter.adapt_answer_to_state_patch(
            rag_result=rag_result,
            current_state=current_state,
        )

        merged_state = _merge_agent_state_patch(
            current_state=current_state,
            patch=patch,
        )

        merged_metadata = merged_state.get("metadata")
        if not isinstance(merged_metadata, dict):
            merged_metadata = {}

        merged_metadata = dict(merged_metadata)
        merged_metadata.update(
            {
                "rag_workflow_integration_used": True,
                "rag_workflow_integration_error": None,
                "rag_workflow_query": effective_query,
                "rag_workflow_domain": effective_domain,
                "rag_workflow_limit": limit,
                "rag_workflow_rerank": rerank,
                "rag_workflow_rerank_top_k": rerank_top_k,
            }
        )
        merged_state["metadata"] = merged_metadata

        return cast(AgentState, merged_state)

    except Exception as exc:
        metadata.update(
            {
                "rag_workflow_integration_used": False,
                "rag_workflow_integration_error": f"{type(exc).__name__}: {exc}",
                "rag_workflow_query": effective_query,
                "rag_workflow_domain": effective_domain,
            }
        )
        current_state["metadata"] = metadata
        current_state["handoff_required"] = True
        current_state["human_handoff"] = True
        current_state["warnings"] = _merge_adapter_text_lists(
            current_state.get("warnings"),
            ["rag_workflow_integration_error"],
        )
        current_state["answer_text"] = (
            current_state.get("answer_text")
            or "系统检索知识库时发生异常，请转人工确认。"
        )
        return cast(AgentState, current_state)


def _merge_agent_state_patch(
    *,
    current_state: dict[str, Any],
    patch: AgentState,
) -> dict[str, Any]:

    merged = dict(current_state)

    for key, value in patch.items():

        if key == "metadata":
            existing_metadata = merged.get("metadata")
            if not isinstance(existing_metadata, dict):
                existing_metadata = {}

            patch_metadata = value if isinstance(value, dict) else {}
            merged["metadata"] = {
                **existing_metadata,
                **patch_metadata,
            }
            continue

        if key in {"warnings", "risk_reasons"}:
            merged[key] = _merge_adapter_text_lists(
                merged.get(key),
                value,
            )
            continue

        if key in {"retrieved_chunks", "source_references"}:
            merged[key] = _merge_adapter_dict_lists(
                merged.get(key),
                value,
                identity_key="chunk_id" if key == "retrieved_chunks" else "source_id",
            )
            continue

        if key == "answer_text":
            merged["answer_text"] = value
            continue

        merged[key] = value

    return merged


def _merge_adapter_text_lists(*values: Any) -> list[str]:
    merged: list[str] = []

    for value in values:
        if value is None:
            continue

        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = value
        elif isinstance(value, tuple):
            items = list(value)
        elif isinstance(value, set):
            items = list(value)
        else:
            items = [value]

        for item in items:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)

    return merged


def _merge_adapter_dict_lists(
    existing: Any,
    incoming: Any,
    *,
    identity_key: str,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for value in [existing, incoming]:
        if not isinstance(value, list):
            continue

        for item in value:
            if not isinstance(item, dict):
                continue

            normalized = dict(item)
            identity = str(normalized.get(identity_key) or normalized.get("chunk_id") or normalized.get("source") or len(merged))

            if identity in seen:
                continue

            seen.add(identity)
            merged.append(normalized)

    return merged
