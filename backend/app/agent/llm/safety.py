"""LLM safety guard.

LLMSafetyGuard evaluates LLM output before it can be used by later workflow
nodes. LLM output is not a fact source and must not create business
commitments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.agent.llm.schemas import (
    DEFAULT_FORBIDDEN_COMMITMENTS,
    LLMResponse,
    detect_forbidden_commitments,
)


@dataclass(frozen=True)
class LLMSafetyResult:
    """LLM safety evaluation result."""

    is_safe: bool
    needs_handoff: bool
    sanitized_content: str
    risk_flags: list[str] = field(default_factory=list)
    risk_reasons: list[str] = field(default_factory=list)
    forbidden_hits: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "is_safe": self.is_safe,
            "needs_handoff": self.needs_handoff,
            "sanitized_content": self.sanitized_content,
            "risk_flags": self.risk_flags,
            "risk_reasons": self.risk_reasons,
            "forbidden_hits": self.forbidden_hits,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class LLMSafetyGuard:
    """Evaluate and guard LLM output."""

    forbidden_commitments: tuple[str, ...] = DEFAULT_FORBIDDEN_COMMITMENTS

    def evaluate_text(
        self,
        text: str,
    ) -> LLMSafetyResult:
        """Evaluate plain text."""

        risk_flags: list[str] = []
        risk_reasons: list[str] = []

        forbidden_hits = detect_forbidden_commitments(
            text,
            self.forbidden_commitments,
        )

        if forbidden_hits:
            risk_flags.append("forbidden_commitment")
            risk_reasons.append(
                "LLM 输出包含明确禁止的业务承诺片段。"
            )

        category_hits = _detect_category_risks(text)

        for flag, reason in category_hits:
            if flag not in risk_flags:
                risk_flags.append(flag)
            if reason not in risk_reasons:
                risk_reasons.append(reason)

        is_safe = len(risk_flags) == 0
        sanitized_content = _sanitize_text(
            text=text,
            forbidden_hits=forbidden_hits,
        )

        return LLMSafetyResult(
            is_safe=is_safe,
            needs_handoff=not is_safe,
            sanitized_content=sanitized_content,
            risk_flags=risk_flags,
            risk_reasons=risk_reasons,
            forbidden_hits=forbidden_hits,
            metadata={
                "guard": "LLMSafetyGuard",
                "checked_text_length": len(text),
            },
        )

    def evaluate_response(
        self,
        response: LLMResponse,
    ) -> LLMSafetyResult:
        """Evaluate LLMResponse."""

        text_result = self.evaluate_text(response.content)
        response_risk_flags = list(response.safety_flags)

        risk_flags = _deduplicate_text_list(
            [
                *response_risk_flags,
                *text_result.risk_flags,
            ]
        )

        risk_reasons = list(text_result.risk_reasons)

        if response.is_safe is False and "client_marked_unsafe" not in risk_flags:
            risk_flags.append("client_marked_unsafe")
            risk_reasons.append("LLMClient 已将该响应标记为不安全。")

        if response.needs_handoff and "client_needs_handoff" not in risk_flags:
            risk_flags.append("client_needs_handoff")
            risk_reasons.append("LLMClient 已要求人工接管。")

        if response.error is not None and "llm_error" not in risk_flags:
            risk_flags.append("llm_error")
            risk_reasons.append("LLMResponse 包含错误信息，需安全降级。")

        is_safe = (
            text_result.is_safe
            and response.is_safe
            and response.error is None
        )
        needs_handoff = (
            text_result.needs_handoff
            or response.needs_handoff
            or not is_safe
        )

        return LLMSafetyResult(
            is_safe=is_safe,
            needs_handoff=needs_handoff,
            sanitized_content=text_result.sanitized_content,
            risk_flags=risk_flags,
            risk_reasons=_deduplicate_text_list(risk_reasons),
            forbidden_hits=text_result.forbidden_hits,
            metadata={
                **text_result.metadata,
                "provider": response.provider,
                "model": response.model,
                "request_id": response.request_id,
            },
        )

    def guard_response(
        self,
        response: LLMResponse,
    ) -> LLMResponse:
        """Return response updated with safety result."""

        safety_result = self.evaluate_response(response)

        metadata = {
            **response.metadata,
            "llm_safety_guard": safety_result.to_dict(),
            "final_response_allowed": False,
            "fact_source_allowed": False,
            "commitment_source_allowed": False,
        }

        if safety_result.is_safe:
            return replace(
                response,
                is_safe=True,
                needs_handoff=response.needs_handoff,
                safety_flags=_deduplicate_text_list(
                    [
                        *response.safety_flags,
                        *safety_result.risk_flags,
                    ]
                ),
                metadata=metadata,
            )

        return replace(
            response,
            content=safety_result.sanitized_content,
            finish_reason="safety_rejected",
            safety_flags=_deduplicate_text_list(
                [
                    *response.safety_flags,
                    *safety_result.risk_flags,
                ]
            ),
            is_safe=False,
            needs_handoff=True,
            metadata=metadata,
        )


def _detect_category_risks(
    text: str,
) -> list[tuple[str, str]]:
    """Detect broader high-risk category expressions."""

    checks: list[tuple[str, str, tuple[str, ...]]] = [
        (
            "unauthorized_price_commitment",
            "LLM 输出疑似包含未授权价格或优惠承诺。",
            (
                r"(最低价|底价|优惠价|折扣价|成交价).{0,12}(给你|就是|包邮|成交)",
                r"(\d+(\.\d+)?\s*元|￥\s*\d+(\.\d+)?).{0,12}(成交|包邮|给你|可以|直接)",
                r"(包邮).{0,8}(成交|直接|可以)",
                r"(?<!不能)直接.{0,8}(成交|下单)",
            ),
        ),
        (
            "logistics_commitment",
            "LLM 输出疑似包含确定性物流或到货承诺。",
            (
                r"(今天|明天|当天|一定).{0,8}(发货|到货|送达)",
                r"(保证|确保|一定).{0,8}(发货|到货|送达|包邮)",
            ),
        ),
        (
            "quality_commitment",
            "LLM 输出疑似包含绝对化质量承诺。",
            (
                r"(保证|确保|一定).{0,8}(不坏|不生锈|不掉漆|耐用)",
                r"(质量很好|放心用|完全没问题)",
            ),
        ),
        (
            "aftersale_commitment",
            "LLM 输出疑似包含售后、退换、赔付承诺。",
            (
                r"(一定|保证|直接).{0,8}(能退|能换|赔|补发|质保)",
                r"(七天无理由|终身质保|一年质保)",
            ),
        ),
    ]

    results: list[tuple[str, str]] = []

    for flag, reason, patterns in checks:
        if any(re.search(pattern, text) for pattern in patterns):
            results.append((flag, reason))

    return results


def _sanitize_text(
    *,
    text: str,
    forbidden_hits: list[str],
) -> str:
    """Sanitize forbidden commitment fragments."""

    sanitized = text

    for hit in forbidden_hits:
        sanitized = sanitized.replace(hit, "[已移除高风险承诺]")

    return sanitized


def _deduplicate_text_list(
    values: list[str],
) -> list[str]:
    """Deduplicate text list while preserving order."""

    result: list[str] = []

    for value in values:
        if value not in result:
            result.append(value)

    return result