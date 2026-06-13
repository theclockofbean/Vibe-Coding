"""LLM intent classifier with safe fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Final

from app.agent.llm.factory import build_llm_client_result_from_env
from app.agent.llm.safety import LLMSafetyGuard
from app.agent.llm.schemas import LLMRequest

ALLOWED_INTENTS: Final[tuple[str, ...]] = (
    "spec",
    "price",
    "logistics",
    "quality",
    "general",
    "escalation",
)

LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.62


@dataclass(frozen=True)
class IntentClassificationResult:
    """Intent classification result."""

    intent: str
    confidence: float
    reason: str
    used_llm: bool = False
    is_valid: bool = True
    fallback_reason: str | None = None
    raw_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "reason": self.reason,
            "used_llm": self.used_llm,
            "is_valid": self.is_valid,
            "fallback_reason": self.fallback_reason,
            "raw_content": self.raw_content,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class LLMIntentClassifier:
    """Classify user intent with LLM only when needed."""

    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD

    def classify(
        self,
        *,
        user_text: str,
        rule_based_intent: str | None = None,
        rule_based_confidence: float | None = None,
    ) -> IntentClassificationResult:
        """Classify intent.

        High-confidence rule-based result wins. LLM is only used when the
        existing router is ambiguous or low confidence.
        """

        normalized_text = user_text.strip()

        if not normalized_text:
            return IntentClassificationResult(
                intent="general",
                confidence=0.0,
                reason="用户输入为空，使用 general 兜底。",
                used_llm=False,
                fallback_reason="empty_user_text",
            )

        if _is_high_confidence_rule_based(
            intent=rule_based_intent,
            confidence=rule_based_confidence,
            threshold=self.low_confidence_threshold,
        ):
            return IntentClassificationResult(
                intent=str(rule_based_intent),
                confidence=float(rule_based_confidence or 0.0),
                reason="rule-based router 高置信命中，未调用 LLM。",
                used_llm=False,
                fallback_reason="rule_based_high_confidence",
            )

        client_result = build_llm_client_result_from_env()

        if not client_result.real_api_enabled:
            fallback = classify_intent_by_keywords(normalized_text)

            return IntentClassificationResult(
                intent=fallback.intent,
                confidence=fallback.confidence,
                reason=fallback.reason,
                used_llm=False,
                fallback_reason=(
                    client_result.metadata.get("fallback_reason")
                    or "real_api_not_enabled"
                ),
                metadata={
                    "llm_factory": client_result.metadata,
                    "llm_factory_warnings": client_result.warnings,
                },
            )

        request = LLMRequest(
            task_type="classify_intent",
            user_text=normalized_text,
            developer_instruction=(
                "请只输出 JSON。intent 必须是 spec、price、logistics、quality、"
                "general、escalation 之一。不要生成业务回答。"
            ),
            structured_facts={
                "allowed_intents": list(ALLOWED_INTENTS),
                "rule_based_intent": rule_based_intent,
                "rule_based_confidence": rule_based_confidence,
            },
            business_rules=[
                "intent classifier 只做分类，不生成业务回答。",
                "不得生成价格、物流、质量或售后承诺。",
            ],
            metadata={
                "classifier": "LLMIntentClassifier",
                "low_confidence_threshold": self.low_confidence_threshold,
            },
            temperature=0.0,
            max_tokens=160,
        )

        raw_response = client_result.client.generate(request)
        guarded_response = LLMSafetyGuard().guard_response(raw_response)

        if guarded_response.error is not None:
            return _fallback_after_llm_failure(
                user_text=normalized_text,
                fallback_reason=f"llm_error: {guarded_response.error}",
                client_result_metadata=client_result.metadata,
                raw_content=guarded_response.content,
            )

        if guarded_response.is_safe is not True:
            return _fallback_after_llm_failure(
                user_text=normalized_text,
                fallback_reason="llm_response_unsafe",
                client_result_metadata=client_result.metadata,
                raw_content=guarded_response.content,
            )

        parsed = parse_llm_intent_content(guarded_response.content)

        if parsed is None:
            return _fallback_after_llm_failure(
                user_text=normalized_text,
                fallback_reason="llm_intent_parse_failed",
                client_result_metadata=client_result.metadata,
                raw_content=guarded_response.content,
            )

        resolved = _resolve_llm_intent_with_local_cues(
            user_text=normalized_text,
            parsed=parsed,
        )

        return IntentClassificationResult(
            intent=resolved.intent,
            confidence=resolved.confidence,
            reason=resolved.reason,
            used_llm=True,
            is_valid=True,
            fallback_reason=None,
            raw_content=guarded_response.content,
            metadata={
                "provider": guarded_response.provider,
                "model": guarded_response.model,
                "latency_ms": guarded_response.latency_ms,
                "llm_factory": client_result.metadata,
                "llm_safety_flags": guarded_response.safety_flags,
                "intent_resolution": resolved.metadata,
            },
        )


def classify_intent_with_llm(
    *,
    user_text: str,
    rule_based_intent: str | None = None,
    rule_based_confidence: float | None = None,
) -> IntentClassificationResult:
    """Convenience wrapper."""

    return LLMIntentClassifier().classify(
        user_text=user_text,
        rule_based_intent=rule_based_intent,
        rule_based_confidence=rule_based_confidence,
    )


def parse_llm_intent_content(
    content: str,
) -> IntentClassificationResult | None:
    """Parse LLM intent JSON content."""

    text = content.strip()

    if not text:
        return None

    lowered = text.lower()

    if lowered in ALLOWED_INTENTS:
        return IntentClassificationResult(
            intent=lowered,
            confidence=0.6,
            reason="LLM 返回了纯 intent 枚举。",
            used_llm=True,
            raw_content=content,
        )

    json_text = _extract_json_object_text(text)

    if json_text is None:
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    intent = str(data.get("intent") or "").strip().lower()

    if intent not in ALLOWED_INTENTS:
        return None

    confidence = _coerce_confidence(data.get("confidence"))
    reason = str(data.get("reason") or "LLM 分类结果。").strip()

    return IntentClassificationResult(
        intent=intent,
        confidence=confidence,
        reason=reason,
        used_llm=True,
        raw_content=content,
    )


def classify_intent_by_keywords(
    user_text: str,
) -> IntentClassificationResult:
    """Local safe keyword fallback classifier."""

    text = user_text.strip().lower()

    keyword_rules: tuple[tuple[str, tuple[str, ...], float], ...] = (
        (
            "price",
            (
                "多少钱",
                "价格",
                "报价",
                "单价",
                "折扣",
                "采购价",
                "成交价",
            ),
            0.78,
        ),
        (
            "logistics",
            (
                "发货",
                "到货",
                "物流",
                "快递",
                "运费",
                "包邮",
                "几天到",
                "几天发",
                "运输",
            ),
            0.76,
        ),
        (
            "quality",
            (
                "质量",
                "材质",
                "材料",
                "外观",
                "表面处理",
                "阳极氧化",
                "安全说明",
                "安全使用",
                "使用风险",
                "检测",
                "检测记录",
                "认证",
                "生锈",
                "掉漆",
                "耐用",
                "划痕",
            ),
            0.76,
        ),
        (
            "spec",
            (
                "sku",
                "规格",
                "尺寸",
                "螺纹",
                "杆长",
                "球径",
                "锥度",
                "m8",
                "m10",
                "m12",
            ),
            0.74,
        ),
        (
            "escalation",
            (
                "人工",
                "客服",
                "投诉",
                "升级",
                "处理不了",
            ),
            0.7,
        ),
    )

    for intent, keywords, confidence in keyword_rules:
        if any(keyword in text for keyword in keywords):
            return IntentClassificationResult(
                intent=intent,
                confidence=confidence,
                reason=f"关键词命中 {intent} 类意图。",
                used_llm=False,
                fallback_reason="keyword_fallback",
            )

    return IntentClassificationResult(
        intent="general",
        confidence=0.45,
        reason="未命中明确业务关键词，使用 general 兜底。",
        used_llm=False,
        fallback_reason="keyword_fallback_general",
    )



def _resolve_llm_intent_with_local_cues(
    *,
    user_text: str,
    parsed: IntentClassificationResult,
) -> IntentClassificationResult:
    """Resolve low-confidence LLM spec intent against local quality cues.

    Real LLMs may classify material / appearance / safety questions as spec
    because they mention material parameters. In this business workflow, those
    questions should be handled by quality when they ask for safety, exterior
    treatment, inspection, certification, durability, or quality interpretation.
    """

    local = classify_intent_by_keywords(user_text)

    if (
        parsed.intent == "spec"
        and parsed.confidence <= 0.8
        and local.intent == "quality"
        and local.confidence >= 0.7
    ):
        return IntentClassificationResult(
            intent="quality",
            confidence=max(local.confidence, min(parsed.confidence, 0.78)),
            reason=(
                "LLM 返回 spec，但用户文本包含材料、外观、安全或检测类质量线索，"
                f"按 quality 处理。原始原因：{parsed.reason}"
            ),
            used_llm=True,
            is_valid=True,
            fallback_reason=None,
            raw_content=parsed.raw_content,
            metadata={
                "resolver": "spec_to_quality_local_cue_resolution",
                "original_llm_intent": parsed.intent,
                "original_llm_confidence": parsed.confidence,
                "local_intent": local.intent,
                "local_confidence": local.confidence,
                "local_reason": local.reason,
            },
        )

    return parsed


def _fallback_after_llm_failure(
    *,
    user_text: str,
    fallback_reason: str,
    client_result_metadata: dict[str, Any],
    raw_content: str | None,
) -> IntentClassificationResult:
    """Fallback after LLM failure."""

    fallback = classify_intent_by_keywords(user_text)

    return IntentClassificationResult(
        intent=fallback.intent,
        confidence=fallback.confidence,
        reason=fallback.reason,
        used_llm=False,
        is_valid=True,
        fallback_reason=fallback_reason,
        raw_content=raw_content,
        metadata={
            "llm_factory": client_result_metadata,
        },
    )


def _is_high_confidence_rule_based(
    *,
    intent: str | None,
    confidence: float | None,
    threshold: float,
) -> bool:
    """Return whether rule-based result is high confidence."""

    if intent not in ALLOWED_INTENTS:
        return False

    if confidence is None:
        return False

    return confidence >= threshold


def _extract_json_object_text(
    text: str,
) -> str | None:
    """Extract first JSON object from text."""

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()

        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start < 0 or end < start:
        return None

    return cleaned[start : end + 1]


def _coerce_confidence(
    value: object,
) -> float:
    """Coerce confidence to 0..1."""

    if isinstance(value, int | float):
        confidence = float(value)
    elif isinstance(value, str):
        try:
            confidence = float(value)
        except ValueError:
            confidence = 0.5
    else:
        confidence = 0.5

    if confidence < 0:
        return 0.0

    if confidence > 1:
        return 1.0

    return confidence