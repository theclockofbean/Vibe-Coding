"""LLM client abstractions and offline implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.agent.llm.schemas import (
    LLMCallTimer,
    LLMRequest,
    LLMResponse,
    build_llm_error_response,
    detect_forbidden_commitments,
)


class LLMClient(Protocol):
    """LLM client protocol."""

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        """Generate structured LLM response."""


class LLMClientError(RuntimeError):
    """LLM client error."""


@dataclass(frozen=True)
class EchoLLMClient:
    """Offline echo client for contract and workflow tests."""

    provider: str = "local"
    model: str = "echo-llm-v1"

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        """Return deterministic echo response."""

        timer = LLMCallTimer()
        forbidden_hits = detect_forbidden_commitments(
            request.user_text,
            request.forbidden_commitments,
        )

        if forbidden_hits:
            return LLMResponse(
                request_id=request.request_id,
                provider=self.provider,
                model=self.model,
                content="检测到高风险承诺表达，LLM 已拒绝生成。",
                finish_reason="safety_rejected",
                latency_ms=timer.elapsed_ms(),
                safety_flags=["forbidden_commitment_detected"],
                is_safe=False,
                needs_handoff=True,
                metadata={
                    "task_type": request.task_type,
                    "forbidden_hits": forbidden_hits,
                    "client": "EchoLLMClient",
                },
            )

        return LLMResponse(
            request_id=request.request_id,
            provider=self.provider,
            model=self.model,
            content=f"[echo:{request.task_type}] {request.user_text}",
            finish_reason="stop",
            usage={
                "prompt_tokens": len(request.user_text),
                "completion_tokens": len(request.user_text),
                "total_tokens": len(request.user_text) * 2,
            },
            latency_ms=timer.elapsed_ms(),
            safety_flags=[],
            is_safe=True,
            needs_handoff=False,
            metadata={
                "task_type": request.task_type,
                "client": "EchoLLMClient",
                "final_response_allowed": False,
            },
        )


@dataclass(frozen=True)
class RuleBasedLLMClient:
    """Offline rule-based client for safety and fallback tests."""

    provider: str = "local"
    model: str = "rule-based-llm-v1"

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        """Generate deterministic safe response."""

        timer = LLMCallTimer()

        try:
            return self._generate_safe_response(
                request=request,
                latency_ms=timer.elapsed_ms(),
            )
        except (RuntimeError, ValueError) as exc:
            return build_llm_error_response(
                request=request,
                provider=self.provider,
                model=self.model,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=timer.elapsed_ms(),
            )

    def _generate_safe_response(
        self,
        *,
        request: LLMRequest,
        latency_ms: int,
    ) -> LLMResponse:
        """Generate deterministic safe response."""

        combined_text = "\n".join(
            [
                request.user_text,
                "\n".join(request.context_blocks),
                str(request.retrieved_chunks),
                str(request.structured_facts),
                "\n".join(request.business_rules),
            ]
        )

        forbidden_hits = detect_forbidden_commitments(
            combined_text,
            request.forbidden_commitments,
        )

        if forbidden_hits:
            return LLMResponse(
                request_id=request.request_id,
                provider=self.provider,
                model=self.model,
                content="检测到可能构成业务承诺的表达，建议转人工或依据正式规则确认。",
                finish_reason="safety_rejected",
                latency_ms=latency_ms,
                safety_flags=[
                    "forbidden_commitment_detected",
                    "needs_handoff",
                ],
                is_safe=False,
                needs_handoff=True,
                metadata={
                    "task_type": request.task_type,
                    "forbidden_hits": forbidden_hits,
                    "client": "RuleBasedLLMClient",
                    "final_response_allowed": False,
                },
            )

        if request.task_type == "echo_test":
            content = f"[rule-echo] {request.user_text}"
        elif request.task_type == "rewrite_safe_answer":
            content = "可基于已确认的结构化事实进行安全改写，但不得新增事实或承诺。"
        elif request.task_type == "summarize_evidence":
            content = self._summarize_evidence(request)
        elif request.task_type == "draft_handoff_note":
            content = "该问题涉及需要人工确认的信息，请人工结合正式数据与业务规则处理。"
        elif request.task_type == "classify_answer_risk":
            content = "当前未检测到禁止承诺片段，仍需以结构化规则和人工确认为准。"
        elif request.task_type == "rule_based_test":
            content = "RuleBasedLLMClient 已按安全规则返回离线测试结果。"
        else:
            raise LLMClientError(f"unsupported task_type: {request.task_type}")

        return LLMResponse(
            request_id=request.request_id,
            provider=self.provider,
            model=self.model,
            content=content,
            finish_reason="stop",
            usage={
                "prompt_tokens": len(combined_text),
                "completion_tokens": len(content),
                "total_tokens": len(combined_text) + len(content),
            },
            latency_ms=latency_ms,
            safety_flags=[],
            is_safe=True,
            needs_handoff=False,
            metadata={
                "task_type": request.task_type,
                "client": "RuleBasedLLMClient",
                "final_response_allowed": False,
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
        )

    def _summarize_evidence(
        self,
        request: LLMRequest,
    ) -> str:
        """Return deterministic evidence summary."""

        chunk_count = len(request.retrieved_chunks)
        fact_count = len(request.structured_facts)

        if chunk_count == 0 and fact_count == 0:
            return "当前证据不足，不能形成事实结论或业务承诺。"

        return (
            f"已接收 {fact_count} 项结构化事实与 {chunk_count} 条 RAG 证据；"
            "仅可用于非承诺性说明，最终结论以结构化数据、业务规则或人工确认为准。"
        )