"""Grounded final response renderer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agent.llm.safety import LLMSafetyGuard
from app.agent.rendering.schemas import (
    DEFAULT_RENDER_BUSINESS_RULES,
    SAFE_FALLBACK_RESPONSE,
    SAFETY_BLOCKED_RESPONSE,
    GroundedRenderInput,
    GroundedRenderOutput,
    make_response_source,
)


@dataclass(frozen=True)
class GroundedRenderer:
    """Render grounded final response.

    The renderer can use structured facts, safe RAG evidence, business rules,
    and optional safe LLM expression support. It must not turn LLM or RAG into a
    fact source or commitment source.
    """

    max_evidence_items: int = 2

    def render(
        self,
        render_input: GroundedRenderInput,
    ) -> GroundedRenderOutput:
        """Render final response with final safety guard."""

        try:
            return self._render_internal(render_input)
        except (RuntimeError, ValueError, TypeError) as exc:
            return _build_fallback_output(
                render_input=render_input,
                fallback_reason=f"{type(exc).__name__}: {exc}",
            )

    def _render_internal(
        self,
        render_input: GroundedRenderInput,
    ) -> GroundedRenderOutput:
        """Render internal response."""

        response_sources = _build_response_sources(render_input)
        response_warnings = _deduplicate_text_list(render_input.warnings)
        pieces: list[str] = []

        base_answer = _optional_text(render_input.answer_text)

        if base_answer is not None:
            pieces.append(base_answer)

        evidence_lines = _build_evidence_lines(
            render_input=render_input,
            max_items=self.max_evidence_items,
        )

        boundary_line = _build_business_boundary_line(render_input)

        if evidence_lines:
            pieces.append("补充说明：" + "；".join(evidence_lines) + "。")

        if boundary_line is not None:
            pieces.append(boundary_line)

        llm_expression = _build_llm_expression_line(render_input)

        if llm_expression is not None:
            pieces.append(llm_expression)
            response_sources.append(
                make_response_source(
                    reference_id="llm_safe_rewrite",
                    source_type="llm_safe_rewrite",
                    source_name="RuleBasedLLMClient",
                    used_for="expression_support",
                    metadata={
                        "fact_source_allowed": False,
                        "commitment_source_allowed": False,
                    },
                )
            )

        if not pieces:
            fallback_output = _build_fallback_output(
                render_input=render_input,
                fallback_reason="empty_render_context",
            )
            return fallback_output

        if response_sources:
            pieces.append(_format_reference_line(response_sources))

        final_response = "\n\n".join(
            piece.strip()
            for piece in pieces
            if piece.strip()
        )

        safety_result = LLMSafetyGuard().evaluate_text(final_response)

        if not safety_result.is_safe:
            return GroundedRenderOutput(
                final_response=SAFETY_BLOCKED_RESPONSE,
                response_sources=response_sources,
                response_warnings=_deduplicate_text_list(
                    [
                        *response_warnings,
                        "grounded render safety blocked",
                    ]
                ),
                risk_flags=safety_result.risk_flags,
                risk_reasons=_deduplicate_text_list(
                    [
                        *render_input.risk_reasons,
                        *safety_result.risk_reasons,
                    ]
                ),
                is_grounded=False,
                used_llm_output=llm_expression is not None,
                needs_handoff=True,
                metadata={
                    **render_input.metadata,
                    "render_mode": "safety_blocked",
                    "render_is_grounded": False,
                    "render_used_llm_output": llm_expression is not None,
                    "render_source_count": len(response_sources),
                    "render_warning_count": len(response_warnings) + 1,
                    "render_safety_blocked": True,
                    "render_fallback_reason": "final_response_safety_blocked",
                    "render_safety_result": safety_result.to_dict(),
                },
            )

        return GroundedRenderOutput(
            final_response=final_response,
            response_sources=response_sources,
            response_warnings=response_warnings,
            risk_flags=[],
            risk_reasons=render_input.risk_reasons,
            is_grounded=True,
            used_llm_output=llm_expression is not None,
            needs_handoff=render_input.handoff_required,
            metadata={
                **render_input.metadata,
                "render_mode": "grounded",
                "render_is_grounded": True,
                "render_used_llm_output": llm_expression is not None,
                "render_source_count": len(response_sources),
                "render_warning_count": len(response_warnings),
                "render_safety_blocked": False,
                "render_fallback_reason": None,
            },
        )


def render_grounded_response(
    render_input: GroundedRenderInput,
) -> GroundedRenderOutput:
    """Convenience wrapper."""

    return GroundedRenderer().render(render_input)


def _build_evidence_lines(
    *,
    render_input: GroundedRenderInput,
    max_items: int,
) -> list[str]:
    """Build supplementary evidence lines from safe RAG chunks."""

    lines: list[str] = []

    for chunk in render_input.retrieved_chunks:
        if chunk.get("allow_answer_reference") is False:
            continue

        summary = _optional_text(chunk.get("summary"))
        content = _optional_text(chunk.get("content"))

        line = summary or content

        if line is None:
            continue

        lines.append(_trim_text(line, max_length=90))

        if len(lines) >= max_items:
            break

    return lines


def _build_business_boundary_line(
    render_input: GroundedRenderInput,
) -> str | None:
    """Build module-level business boundary line."""

    selected_module = render_input.selected_module

    if selected_module == "price":
        return (
            "价格、折扣、成交价和有效期必须以正式价格表、授权报价或人工确认为准。"
        )

    if selected_module == "logistics":
        return (
            "物流时效、承运商、运费和配送范围需结合库存、地址、承运商规则或人工确认。"
        )

    if selected_module == "quality":
        return (
            "质量、外观、耐久表现和使用结果不能仅由 RAG 或 LLM 判断，"
            "需以结构化资料、检测记录或人工确认为准。"
        )

    if render_input.handoff_required:
        return "该问题涉及需要人工确认的信息，请结合正式数据和业务规则处理。"

    return None


def _build_llm_expression_line(
    render_input: GroundedRenderInput,
) -> str | None:
    """Build optional safe LLM expression support line."""

    llm_output = _optional_text(render_input.llm_output)

    if llm_output is None:
        return None

    llm_response = render_input.llm_response

    if llm_response.get("is_safe") is not True:
        return None

    if llm_response.get("error") is not None:
        return None

    metadata = _as_dict(llm_response.get("metadata"))

    if metadata.get("fact_source_allowed") is True:
        return None

    if metadata.get("commitment_source_allowed") is True:
        return None

    if render_input.selected_module in {"price", "logistics", "quality"}:
        return "处理建议：" + _trim_text(llm_output, max_length=80)

    if render_input.handoff_required:
        return "处理建议：" + _trim_text(llm_output, max_length=80)

    return None


def _build_response_sources(
    render_input: GroundedRenderInput,
) -> list[dict[str, Any]]:
    """Build normalized response sources."""

    sources: list[dict[str, Any]] = []

    for reference in render_input.source_references:
        source = _source_from_reference(reference)

        if source is not None:
            sources.append(source)

    for chunk in render_input.retrieved_chunks:
        chunk_source = _source_from_chunk(chunk)

        if chunk_source is not None:
            sources.append(chunk_source)

    if render_input.business_rules:
        sources.append(
            make_response_source(
                reference_id="render_business_rules",
                source_type="business_rule",
                source_name="GroundedRenderer",
                used_for="business_boundary",
                metadata={
                    "rule_count": len(render_input.business_rules),
                    "rules": list(DEFAULT_RENDER_BUSINESS_RULES),
                },
            )
        )

    return _deduplicate_sources(sources)


def _source_from_reference(
    reference: dict[str, Any],
) -> dict[str, Any] | None:
    """Build source from existing source reference."""

    source_type = _optional_text(reference.get("source_type"))
    source_table = _optional_text(reference.get("source_table"))

    if source_type == "rag_chunk":
        reference_id = _optional_text(reference.get("reference_id"))
        if reference_id is None:
            return None

        return make_response_source(
            reference_id=reference_id,
            source_type="rag_chunk",
            source_name=_optional_text(reference.get("source_name")),
            doc_title=_optional_text(reference.get("doc_title")),
            module=_optional_text(reference.get("module")),
            score=_optional_float(reference.get("score")),
            used_for="supplementary_explanation",
        )

    if source_table == "products" or source_type == "products":
        reference_id = (
            _optional_text(reference.get("reference_id"))
            or _optional_text(reference.get("query_value"))
            or "products"
        )

        return make_response_source(
            reference_id=reference_id,
            source_type="products",
            source_name="products",
            used_for="structured_fact",
        )

    reference_id = _optional_text(reference.get("reference_id"))

    if reference_id is None:
        return None

    return make_response_source(
        reference_id=reference_id,
        source_type=source_type or "unknown",
        source_name=_optional_text(reference.get("source_name")),
        used_for=_optional_text(reference.get("used_for")) or "structured_fact",
    )


def _source_from_chunk(
    chunk: dict[str, Any],
) -> dict[str, Any] | None:
    """Build source from retrieved chunk."""

    if chunk.get("allow_answer_reference") is False:
        return None

    chunk_id = _optional_text(chunk.get("chunk_id"))

    if chunk_id is None:
        return None

    return make_response_source(
        reference_id=chunk_id,
        source_type="rag_chunk",
        source_name=_optional_text(chunk.get("source_name")),
        doc_title=_optional_text(chunk.get("doc_title")),
        module=_optional_text(chunk.get("module")),
        score=_optional_float(chunk.get("score")),
        used_for="supplementary_explanation",
    )


def _format_reference_line(
    sources: list[dict[str, Any]],
) -> str:
    """Format concise reference line."""

    reference_ids: list[str] = []

    for source in sources:
        reference_id = _optional_text(source.get("reference_id"))

        if reference_id is None:
            continue

        if reference_id not in reference_ids:
            reference_ids.append(reference_id)

    if not reference_ids:
        return ""

    return "参考来源：" + "；".join(reference_ids) + "。"


def _build_fallback_output(
    *,
    render_input: GroundedRenderInput,
    fallback_reason: str,
) -> GroundedRenderOutput:
    """Build safe fallback output."""

    base_answer = _optional_text(render_input.answer_text)
    final_response = base_answer or SAFE_FALLBACK_RESPONSE

    needs_handoff = render_input.handoff_required or base_answer is None

    return GroundedRenderOutput(
        final_response=final_response,
        response_sources=_build_response_sources(render_input),
        response_warnings=_deduplicate_text_list(
            [
                *render_input.warnings,
                "grounded render fallback",
            ]
        ),
        risk_flags=[],
        risk_reasons=render_input.risk_reasons,
        is_grounded=base_answer is not None,
        used_llm_output=False,
        needs_handoff=needs_handoff,
        metadata={
            **render_input.metadata,
            "render_mode": (
                "fallback_answer_text"
                if base_answer is not None
                else "fallback_safe_response"
            ),
            "render_is_grounded": base_answer is not None,
            "render_used_llm_output": False,
            "render_source_count": len(_build_response_sources(render_input)),
            "render_warning_count": len(render_input.warnings) + 1,
            "render_safety_blocked": False,
            "render_fallback_reason": fallback_reason,
        },
    )


def _deduplicate_sources(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate sources by source_type and reference_id."""

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for source in sources:
        source_type = str(source.get("source_type") or "")
        reference_id = str(source.get("reference_id") or "")
        key = (source_type, reference_id)

        if key in seen:
            continue

        seen.add(key)
        result.append(source)

    return result


def _deduplicate_text_list(
    values: list[str],
) -> list[str]:
    """Deduplicate text list preserving order."""

    result: list[str] = []

    for value in values:
        if value not in result:
            result.append(value)

    return result


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


def _optional_float(
    value: object,
) -> float | None:
    """Return optional float."""

    if isinstance(value, int | float):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None


def _trim_text(
    text: str,
    *,
    max_length: int,
) -> str:
    """Trim text for response."""

    normalized = " ".join(text.split())

    if len(normalized) <= max_length:
        return normalized

    return normalized[: max_length - 1] + "…"


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