"""LLM request and response schemas.

LLM output is not a fact source and must not directly become final_response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Final
from uuid import uuid4

SUPPORTED_LLM_TASK_TYPES: Final[set[str]] = {
    "rewrite_safe_answer",
    "summarize_evidence",
    "draft_handoff_note",
    "classify_answer_risk",
    "classify_intent",
    "echo_test",
    "rule_based_test",
}

DISALLOWED_LLM_TASK_TYPES: Final[set[str]] = {
    "freeform_final_answer",
    "price_generation",
    "logistics_commitment_generation",
    "quality_guarantee_generation",
    "aftersale_commitment_generation",
}

DEFAULT_FORBIDDEN_COMMITMENTS: Final[tuple[str, ...]] = (
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


class LLMContractError(ValueError):
    """LLM schema contract error."""


@dataclass(frozen=True)
class LLMRequest:
    """Structured LLM request.

    LLMRequest must carry explicit safety boundaries. LLM must not invent facts
    or create business commitments.
    """

    task_type: str
    user_text: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    system_instruction: str = (
        "你是受控语言生成组件。不得编造事实，不得生成业务承诺。"
    )
    developer_instruction: str = (
        "结构化事实、业务规则、人工确认优先；LLM 输出不是事实来源。"
    )
    context_blocks: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    structured_facts: dict[str, Any] = field(default_factory=dict)
    business_rules: list[str] = field(default_factory=list)
    forbidden_commitments: tuple[str, ...] = DEFAULT_FORBIDDEN_COMMITMENTS
    temperature: float = 0.0
    max_tokens: int = 512
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate request contract."""

        if not self.request_id.strip():
            raise LLMContractError("request_id must not be blank")

        if self.task_type in DISALLOWED_LLM_TASK_TYPES:
            raise LLMContractError(f"disallowed LLM task_type: {self.task_type}")

        if self.task_type not in SUPPORTED_LLM_TASK_TYPES:
            raise LLMContractError(f"unsupported LLM task_type: {self.task_type}")

        if self.temperature < 0:
            raise LLMContractError("temperature must not be negative")

        if self.max_tokens <= 0:
            raise LLMContractError("max_tokens must be positive")

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "request_id": self.request_id,
            "task_type": self.task_type,
            "user_text": self.user_text,
            "system_instruction": self.system_instruction,
            "developer_instruction": self.developer_instruction,
            "context_blocks": self.context_blocks,
            "retrieved_chunks": self.retrieved_chunks,
            "structured_facts": self.structured_facts,
            "business_rules": self.business_rules,
            "forbidden_commitments": list(self.forbidden_commitments),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class LLMResponse:
    """Structured LLM response.

    content is not final_response. Unsafe responses must not be rendered.
    """

    request_id: str
    provider: str
    model: str
    content: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    safety_flags: list[str] = field(default_factory=list)
    is_safe: bool = True
    needs_handoff: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        """Validate response contract."""

        if not self.request_id.strip():
            raise LLMContractError("request_id must not be blank")

        if not self.provider.strip():
            raise LLMContractError("provider must not be blank")

        if not self.model.strip():
            raise LLMContractError("model must not be blank")

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "safety_flags": self.safety_flags,
            "is_safe": self.is_safe,
            "needs_handoff": self.needs_handoff,
            "metadata": self.metadata,
            "error": self.error,
        }


@dataclass(frozen=True)
class LLMCallTimer:
    """Small helper for latency measurement."""

    started_at: float = field(default_factory=perf_counter)

    def elapsed_ms(self) -> int:
        """Return elapsed milliseconds."""

        return int((perf_counter() - self.started_at) * 1000)


def detect_forbidden_commitments(
    text: str,
    forbidden_commitments: tuple[str, ...] = DEFAULT_FORBIDDEN_COMMITMENTS,
) -> list[str]:
    """Return forbidden commitment fragments found in text."""

    return [
        fragment
        for fragment in forbidden_commitments
        if fragment in text
    ]


def build_llm_error_response(
    *,
    request: LLMRequest,
    provider: str,
    model: str,
    error: str,
    latency_ms: int = 0,
) -> LLMResponse:
    """Build safe error response."""

    return LLMResponse(
        request_id=request.request_id,
        provider=provider,
        model=model,
        content="LLM 调用失败，已安全降级。",
        finish_reason="error",
        latency_ms=latency_ms,
        safety_flags=["llm_error"],
        is_safe=False,
        needs_handoff=False,
        metadata={
            "fallback_allowed": True,
        },
        error=error,
    )