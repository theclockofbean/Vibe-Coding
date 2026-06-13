"""Render context builder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.agent.rendering.schemas import (
    DEFAULT_RENDER_BUSINESS_RULES,
    GroundedRenderInput,
)


@dataclass(frozen=True)
class RenderContextBuilder:
    """Build GroundedRenderInput from AgentState-like mapping."""

    def from_state(
        self,
        state: Mapping[str, Any],
    ) -> GroundedRenderInput:
        """Build GroundedRenderInput from state."""

        module_payload = _as_dict(state.get("module_payload"))
        structured_facts = _extract_structured_facts(module_payload)

        retrieved_chunks = _extract_safe_retrieved_chunks(
            state.get("retrieved_chunks")
        )
        source_references = _extract_source_references(
            state.get("source_references")
        )

        llm_response = _as_dict(state.get("llm_response"))
        llm_output = _extract_allowed_llm_output(
            llm_output=_optional_text(state.get("llm_output")),
            llm_response=llm_response,
        )

        metadata = _as_dict(state.get("metadata"))
        metadata = {
            **metadata,
            "render_context_builder": "RenderContextBuilder",
            "render_llm_output_allowed": llm_output is not None,
            "render_structured_fact_count": len(structured_facts),
            "render_retrieved_chunk_count": len(retrieved_chunks),
            "render_source_reference_count": len(source_references),
        }

        return GroundedRenderInput(
            session_id=_optional_text(state.get("session_id")),
            user_text=_text_or_empty(state.get("user_text")),
            selected_module=_optional_text(state.get("selected_module")),
            handler_status=_optional_text(state.get("handler_status")),
            parse_status=_optional_text(state.get("parse_status")),
            route_status=_optional_text(state.get("route_status")),
            handoff_required=bool(state.get("handoff_required")),
            answer_text=_optional_text(state.get("answer_text")),
            structured_facts=structured_facts,
            retrieved_chunks=retrieved_chunks,
            source_references=source_references,
            llm_output=llm_output,
            llm_response=llm_response,
            business_rules=list(DEFAULT_RENDER_BUSINESS_RULES),
            risk_reasons=_as_text_list(state.get("risk_reasons")),
            warnings=_as_text_list(state.get("warnings")),
            metadata=metadata,
        )


def build_grounded_render_input(
    state: Mapping[str, Any],
) -> GroundedRenderInput:
    """Convenience wrapper."""

    return RenderContextBuilder().from_state(state)


def _extract_structured_facts(
    module_payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract structured facts from module_payload.

    LLM output is intentionally excluded from structured_facts.
    """

    ignored_keys = {
        "answer_text",
        "errors",
        "warnings",
        "source_references",
    }

    facts: dict[str, Any] = {}

    for key, value in module_payload.items():
        key_text = str(key)

        if key_text in ignored_keys:
            continue

        if _is_empty_value(value):
            continue

        facts[key_text] = _normalize_value(value)

    return facts


def _extract_safe_retrieved_chunks(
    value: object,
) -> list[dict[str, Any]]:
    """Extract RAG chunks allowed for answer reference."""

    chunks = _as_dict_list(value)
    result: list[dict[str, Any]] = []

    for chunk in chunks:
        if chunk.get("is_active") is False:
            continue

        if chunk.get("allow_answer_reference") is False:
            continue

        normalized = {
            str(key): _normalize_value(item_value)
            for key, item_value in chunk.items()
            if not _is_empty_value(item_value)
        }

        normalized["used_for"] = "supplementary_explanation"
        result.append(normalized)

    return result


def _extract_source_references(
    value: object,
) -> list[dict[str, Any]]:
    """Extract source references."""

    references = _as_dict_list(value)
    result: list[dict[str, Any]] = []

    for reference in references:
        normalized = {
            str(key): _normalize_value(item_value)
            for key, item_value in reference.items()
            if not _is_empty_value(item_value)
        }

        source_type = str(normalized.get("source_type") or "")

        if source_type == "rag_chunk":
            normalized["used_for"] = "supplementary_explanation"
        elif normalized.get("source_table") == "products":
            normalized["source_type"] = "products"
            normalized["used_for"] = "structured_fact"
        else:
            normalized.setdefault("used_for", "structured_fact")

        result.append(normalized)

    return result


def _extract_allowed_llm_output(
    *,
    llm_output: str | None,
    llm_response: dict[str, Any],
) -> str | None:
    """Return LLM output only when it is safe expression support."""

    if llm_output is None:
        return None

    if llm_response.get("is_safe") is not True:
        return None

    if llm_response.get("error") is not None:
        return None

    metadata = _as_dict(llm_response.get("metadata"))

    if metadata.get("fact_source_allowed") is True:
        return None

    if metadata.get("commitment_source_allowed") is True:
        return None

    return llm_output


def _as_dict(
    value: object,
) -> dict[str, Any]:
    """Return dict with string keys."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _as_dict_list(
    value: object,
) -> list[dict[str, Any]]:
    """Return list of dictionaries."""

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


def _as_text_list(
    value: object,
) -> list[str]:
    """Return text list."""

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
        if str(item).strip()
    ]


def _optional_text(
    value: object,
) -> str | None:
    """Return optional stripped text."""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def _text_or_empty(
    value: object,
) -> str:
    """Return text or empty string."""

    if value is None:
        return ""

    return str(value).strip()


def _is_empty_value(
    value: object,
) -> bool:
    """Return whether value should be ignored."""

    if value is None:
        return True

    if isinstance(value, str) and not value.strip():
        return True

    if isinstance(value, list | dict | tuple | set) and len(value) == 0:
        return True

    return False


def _normalize_value(
    value: object,
) -> Any:
    """Normalize nested values for serialization."""

    if isinstance(value, dict):
        return {
            str(key): _normalize_value(item_value)
            for key, item_value in value.items()
            if not _is_empty_value(item_value)
        }

    if isinstance(value, list):
        return [
            _normalize_value(item)
            for item in value
            if not _is_empty_value(item)
        ]

    if isinstance(value, tuple | set):
        return [
            _normalize_value(item)
            for item in value
            if not _is_empty_value(item)
        ]

    return value