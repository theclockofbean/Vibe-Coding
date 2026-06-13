"""Patch workflow IntentNode with LLM intent fallback.

This patch is tolerant of different intent_node return expressions.
"""

from __future__ import annotations

from pathlib import Path


target = Path("app/agent/workflow.py")
content = target.read_text(encoding="utf-8")


def patch_intent_node(source: str) -> str:
    """Insert LLM intent fallback before the final return of intent_node."""

    if "_apply_llm_intent_fallback_if_needed(new_state)" in source:
        return source

    start = source.index("    def intent_node(")

    try:
        end = source.index("\n    def route_node(", start)
    except ValueError as exc:
        raise RuntimeError("route_node anchor not found") from exc

    method = source[start:end]
    lines = method.splitlines(keepends=True)

    return_index: int | None = None

    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].lstrip()

        if lines[index].startswith("        return ") and stripped.startswith("return "):
            return_index = index
            break

    if return_index is None:
        raise RuntimeError("no final return statement found in intent_node")

    insertion = [
        "\n",
        "        _apply_llm_intent_fallback_if_needed(new_state)\n",
        "\n",
    ]

    lines[return_index:return_index] = insertion
    patched_method = "".join(lines)

    return source[:start] + patched_method + source[end:]


def patch_helper(source: str) -> str:
    """Add helper functions once."""

    if "def _apply_llm_intent_fallback_if_needed(" in source:
        return source

    helper_anchor = "\ndef _run_grounded_render_for_state("

    helper = '''

def _apply_llm_intent_fallback_if_needed(
    state: AgentState,
) -> None:
    """Apply LLM intent fallback for low-confidence intent routing.

    Conservative policy:
    - high-confidence rule-based routing wins;
    - LLM output must be a valid enum;
    - LLM failure keeps the existing route unchanged.
    """

    import os

    from app.agent.llm.intent_classifier import (
        ALLOWED_INTENTS,
        LLMIntentClassifier,
    )

    metadata = _ensure_metadata(state)

    enabled = _workflow_llm_intent_env_bool(
        "LLM_INTENT_CLASSIFIER_ENABLED",
        default=True,
    )

    metadata["llm_intent_classifier_enabled"] = enabled

    if not enabled:
        metadata["llm_intent_classifier_used"] = False
        metadata["llm_intent_fallback_reason"] = "llm_intent_classifier_disabled"
        return

    user_text = _optional_state_str(state.get("user_text")) or ""
    rule_based_intent = _workflow_llm_intent_current_intent(state)
    rule_based_confidence = _workflow_llm_intent_rule_confidence(
        state=state,
        rule_based_intent=rule_based_intent,
    )

    force_llm_classifier = bool(metadata.get("force_llm_intent_classifier"))

    if force_llm_classifier:
        rule_based_confidence = 0.0

    try:
        result = LLMIntentClassifier().classify(
            user_text=user_text,
            rule_based_intent=rule_based_intent,
            rule_based_confidence=rule_based_confidence,
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        metadata["llm_intent_classifier_used"] = False
        metadata["llm_intent_fallback_reason"] = (
            f"{type(exc).__name__}: {exc}"
        )
        return

    result_dict = result.to_dict()
    metadata["llm_intent_result"] = result_dict
    metadata["llm_intent_classifier_used"] = result.used_llm
    metadata["llm_intent"] = result.intent
    metadata["llm_intent_confidence"] = result.confidence
    metadata["llm_intent_reason"] = result.reason
    metadata["llm_intent_fallback_reason"] = result.fallback_reason

    if result.metadata:
        metadata["llm_intent_metadata"] = result.metadata

    if not result.is_valid:
        return

    if result.intent not in ALLOWED_INTENTS:
        metadata["llm_intent_fallback_reason"] = "invalid_intent_enum"
        return

    should_apply_result = result.used_llm or force_llm_classifier

    if not should_apply_result:
        return

    previous_intent = _workflow_llm_intent_current_intent(state)
    state["intent"] = result.intent

    if result.intent in {"spec", "price", "logistics", "quality"}:
        state["selected_module"] = result.intent
        state["candidate_modules"] = [result.intent]
        state["route_confidence"] = result.confidence
    elif result.intent == "general":
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]
        state["route_confidence"] = result.confidence
    elif result.intent == "escalation":
        state["selected_module"] = "general"
        state["candidate_modules"] = ["general"]
        state["route_confidence"] = result.confidence
        state["handoff_required"] = True
        state["human_handoff"] = True

    metadata["llm_intent_applied"] = True
    metadata["llm_intent_previous_intent"] = previous_intent
    metadata["llm_intent_applied_intent"] = result.intent


def _workflow_llm_intent_current_intent(
    state: AgentState,
) -> str | None:
    """Return current rule-based intent."""

    intent = _optional_state_str(state.get("intent"))

    if intent:
        return intent

    selected_module = _optional_state_str(state.get("selected_module"))

    if selected_module:
        return selected_module

    return None


def _workflow_llm_intent_rule_confidence(
    *,
    state: AgentState,
    rule_based_intent: str | None,
) -> float | None:
    """Infer rule-based confidence from state and metadata."""

    metadata = _ensure_metadata(state)

    for value in (
        state.get("route_confidence"),
        metadata.get("route_confidence"),
        metadata.get("intent_confidence"),
    ):
        confidence = _workflow_llm_intent_optional_float(value)

        if confidence is not None:
            return confidence

    if metadata.get("force_llm_intent_classifier") is True:
        return 0.0

    matched_signals = _as_text_list(state.get("matched_signals"))

    if rule_based_intent in {"spec", "price", "logistics", "quality"}:
        if matched_signals:
            return 0.9
        return 0.66

    if rule_based_intent == "general":
        return 0.45

    return None


def _workflow_llm_intent_env_bool(
    key: str,
    *,
    default: bool,
) -> bool:
    """Read boolean env var."""

    value = os.getenv(key)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _workflow_llm_intent_optional_float(
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

'''

    if helper_anchor not in source:
        raise RuntimeError("grounded render helper anchor not found")

    return source.replace(helper_anchor, helper + helper_anchor, 1)


content = patch_intent_node(content)
content = patch_helper(content)

target.write_text(content, encoding="utf-8")

print("patched workflow IntentNode with LLM intent fallback")