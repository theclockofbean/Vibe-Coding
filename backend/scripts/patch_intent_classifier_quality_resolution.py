"""Patch LLM intent classifier quality/spec conflict resolution."""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/llm/intent_classifier.py")
content = target.read_text(encoding="utf-8")

old_keywords = '''                "质量",
                "材质",
                "表面处理",
                "阳极氧化",
                "生锈",
                "掉漆",
                "耐用",
                "划痕",
                "检测",
'''

new_keywords = '''                "质量",
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
'''

if old_keywords not in content:
    raise RuntimeError("quality keyword block not found")

content = content.replace(old_keywords, new_keywords, 1)

old_return = '''        return IntentClassificationResult(
            intent=parsed.intent,
            confidence=parsed.confidence,
            reason=parsed.reason,
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
            },
        )
'''

new_return = '''        resolved = _resolve_llm_intent_with_local_cues(
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
'''

if old_return not in content:
    raise RuntimeError("parsed intent return block not found")

content = content.replace(old_return, new_return, 1)

helper_anchor = "\ndef _fallback_after_llm_failure("

helper = '''

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

'''

if "def _resolve_llm_intent_with_local_cues(" not in content:
    if helper_anchor not in content:
        raise RuntimeError("fallback helper anchor not found")

    content = content.replace(helper_anchor, helper + helper_anchor, 1)

target.write_text(content, encoding="utf-8")

print("patched intent classifier quality/spec conflict resolution")