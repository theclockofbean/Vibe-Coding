"""Grounded rendering schemas.

Grounded rendering turns structured facts, safe RAG evidence, business rules,
and optional safe LLM expression support into an auditable final response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

SAFE_FALLBACK_RESPONSE: Final[str] = (
    "当前信息不足，无法形成可靠答复。请补充 SKU、数量、收货地区或具体问题后转人工确认。"
)

SAFETY_BLOCKED_RESPONSE: Final[str] = (
    "该问题涉及需要进一步确认的信息。为避免给出未经授权的业务承诺，"
    "请转人工结合正式数据和业务规则处理。"
)

DEFAULT_RENDER_BUSINESS_RULES: Final[tuple[str, ...]] = (
    "价格类：不能直接报价，需正式价格表、授权报价或人工确认。",
    "物流类：不能承诺发货、到货、包邮，需结合库存、地址、承运商和人工确认。",
    "质量类：不能承诺不坏、不生锈、不掉漆、耐久年限，需以结构化资料、检测记录或人工确认为准。",
    "售后类：不能承诺退换、质保、赔付、补发，需以正式售后规则或人工确认为准。",
    "RAG 只能作为补充说明来源，不作为业务承诺来源。",
    "LLM 只能辅助表达，不作为事实来源。",
)


class GroundedRenderContractError(ValueError):
    """Grounded render schema contract error."""


@dataclass(frozen=True)
class GroundedRenderInput:
    """Input for grounded rendering."""

    session_id: str | None = None
    user_text: str = ""
    selected_module: str | None = None
    handler_status: str | None = None
    parse_status: str | None = None
    route_status: str | None = None
    handoff_required: bool = False
    answer_text: str | None = None
    structured_facts: dict[str, Any] = field(default_factory=dict)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    source_references: list[dict[str, Any]] = field(default_factory=list)
    llm_output: str | None = None
    llm_response: dict[str, Any] = field(default_factory=dict)
    business_rules: list[str] = field(
        default_factory=lambda: list(DEFAULT_RENDER_BUSINESS_RULES)
    )
    risk_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate render input."""

        if self.selected_module is not None and not self.selected_module.strip():
            raise GroundedRenderContractError(
                "selected_module must be None or non-blank"
            )

        if self.handler_status is not None and not self.handler_status.strip():
            raise GroundedRenderContractError(
                "handler_status must be None or non-blank"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "session_id": self.session_id,
            "user_text": self.user_text,
            "selected_module": self.selected_module,
            "handler_status": self.handler_status,
            "parse_status": self.parse_status,
            "route_status": self.route_status,
            "handoff_required": self.handoff_required,
            "answer_text": self.answer_text,
            "structured_facts": self.structured_facts,
            "retrieved_chunks": self.retrieved_chunks,
            "source_references": self.source_references,
            "llm_output": self.llm_output,
            "llm_response": self.llm_response,
            "business_rules": self.business_rules,
            "risk_reasons": self.risk_reasons,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class GroundedRenderOutput:
    """Output of grounded rendering."""

    final_response: str
    response_sources: list[dict[str, Any]] = field(default_factory=list)
    response_warnings: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    risk_reasons: list[str] = field(default_factory=list)
    is_grounded: bool = True
    used_llm_output: bool = False
    needs_handoff: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate render output."""

        if not self.final_response.strip():
            raise GroundedRenderContractError("final_response must not be blank")

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "final_response": self.final_response,
            "response_sources": self.response_sources,
            "response_warnings": self.response_warnings,
            "risk_flags": self.risk_flags,
            "risk_reasons": self.risk_reasons,
            "is_grounded": self.is_grounded,
            "used_llm_output": self.used_llm_output,
            "needs_handoff": self.needs_handoff,
            "metadata": self.metadata,
        }


def make_response_source(
    *,
    reference_id: str,
    source_type: str,
    used_for: str,
    source_name: str | None = None,
    doc_title: str | None = None,
    module: str | None = None,
    score: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build normalized response source."""

    source: dict[str, Any] = {
        "reference_id": reference_id,
        "source_type": source_type,
        "used_for": used_for,
    }

    if source_name is not None:
        source["source_name"] = source_name

    if doc_title is not None:
        source["doc_title"] = doc_title

    if module is not None:
        source["module"] = module

    if score is not None:
        source["score"] = score

    if metadata:
        source["metadata"] = metadata

    return source