"""Agent state contract.

AgentState is an internal workflow state object for the future LangGraph agent.

It is not a database model, not an API request model, and not an LLM prompt.
It does not call an LLM, generate business answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

from typing import Any, Final, TypedDict


class AgentState(TypedDict, total=False):
    """Internal agent workflow state."""

    session_id: str | None
    conversation_id: int | None
    channel: str | None
    user_id: str | None

    user_text: str
    normalized_text: str | None

    conversation_history: list[dict[str, Any]]

    intent: str | None
    selected_module: str | None
    candidate_modules: list[str]
    matched_signals: list[str]
    matched_sku: str | None

    route_status: str | None
    route_confidence: float | None
    parse_status: str | None
    handler_status: str | None

    retrieved_chunks: list[dict[str, Any]]

    source_references: list[dict[str, Any]]
    module_payload: dict[str, Any] | None

    answer_text: str | None
    final_response: str | None

    handoff_required: bool
    human_handoff: bool
    handoff_ticket_id: int | None
    handoff_ticket_no: str | None

    risk_triggered: bool
    risk_reasons: list[str]

    user_message_id: int | None
    assistant_message_id: int | None

    warnings: list[str]
    errors: list[str]

    metadata: dict[str, Any]

    # LLM fields. LLM output is not a fact source and must not directly become
    # final_response.
    llm_request: dict[str, Any]
    llm_response: dict[str, Any]
    llm_output: str | None
    llm_safety_flags: list[str]
    llm_used: bool
    llm_error: str | None

    # Grounded render fields. Grounded render output is the audited final
    # response layer.
    render_input: dict[str, Any]
    render_output: dict[str, Any]
    response_sources: list[dict[str, Any]]
    response_warnings: list[str]
    render_risk_flags: list[str]
    render_used_llm_output: bool
    is_grounded_response: bool


FORBIDDEN_COMMITMENT_FRAGMENTS: Final[tuple[str, ...]] = (
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


def create_initial_agent_state(
    *,
    session_id: str | None,
    channel: str | None,
    user_id: str | None,
    user_text: str,
) -> AgentState:
    """Create a safe initial AgentState."""

    normalized_user_text = _normalize_text(user_text)

    return AgentState(
        session_id=_optional_clean_text(session_id),
        conversation_id=None,
        channel=_optional_clean_text(channel),
        user_id=_optional_clean_text(user_id),
        user_text=user_text,
        normalized_text=normalized_user_text,
        conversation_history=[],
        intent=None,
        selected_module=None,
        candidate_modules=[],
        matched_signals=[],
        matched_sku=None,
        route_status=None,
        route_confidence=None,
        parse_status=None,
        handler_status=None,
        retrieved_chunks=[],
        source_references=[],
        module_payload=None,
        answer_text=None,
        final_response=None,
        handoff_required=False,
        human_handoff=False,
        handoff_ticket_id=None,
        handoff_ticket_no=None,
        risk_triggered=False,
        risk_reasons=[],
        user_message_id=None,
        assistant_message_id=None,
        warnings=[],
        errors=[],
        metadata={},
    )


def apply_conversation_context(
    state: AgentState,
    *,
    conversation_id: int | None,
    conversation_history: list[dict[str, Any]],
) -> AgentState:
    """Attach conversation context to state."""

    state["conversation_id"] = conversation_id
    state["conversation_history"] = _list_of_dict(conversation_history)

    return state


def apply_unified_payload(
    state: AgentState,
    *,
    payload: dict[str, Any],
) -> AgentState:
    """Apply current Unified Agent payload fields to AgentState."""

    state["session_id"] = _optional_text(
        payload.get("session_id"),
        fallback=state.get("session_id"),
    )
    state["conversation_id"] = _optional_int(
        payload.get("conversation_id"),
        fallback=state.get("conversation_id"),
    )
    state["selected_module"] = _optional_text(payload.get("selected_module"))
    state["route_status"] = _optional_text(payload.get("route_status"))
    state["route_confidence"] = _optional_float(payload.get("route_confidence"))
    state["parse_status"] = _optional_text(payload.get("parse_status"))
    state["handler_status"] = _optional_text(payload.get("handler_status"))

    state["candidate_modules"] = _list_of_text(
        payload.get("candidate_modules"),
    )
    state["matched_signals"] = _list_of_text(payload.get("matched_signals"))
    state["matched_sku"] = _optional_text(payload.get("matched_sku"))

    state["source_references"] = _list_of_dict(
        payload.get("source_references"),
    )
    state["module_payload"] = _optional_dict(payload.get("module_payload"))

    state["answer_text"] = _optional_text(payload.get("answer_text"))
    state["final_response"] = _optional_text(
        payload.get("final_response"),
        fallback=state.get("answer_text"),
    )

    state["handoff_required"] = _bool_value(payload.get("handoff_required"))
    state["human_handoff"] = state["handoff_required"]
    state["handoff_ticket_id"] = _optional_int(
        payload.get("handoff_ticket_id"),
    )
    state["handoff_ticket_no"] = _optional_text(
        payload.get("handoff_ticket_no"),
    )

    state["user_message_id"] = _optional_int(payload.get("user_message_id"))
    state["assistant_message_id"] = _optional_int(
        payload.get("assistant_message_id"),
    )

    state["warnings"] = _merge_text_lists(
        _list_of_text(state.get("warnings")),
        _list_of_text(payload.get("warnings")),
    )
    state["errors"] = _merge_text_lists(
        _list_of_text(state.get("errors")),
        _list_of_text(payload.get("errors")),
    )

    return state


def apply_retrieved_chunks(
    state: AgentState,
    *,
    retrieved_chunks: list[dict[str, Any]],
) -> AgentState:
    """Attach RAG retrieval chunks to state."""

    state["retrieved_chunks"] = _list_of_dict(retrieved_chunks)

    return state


def apply_risk_control(
    state: AgentState,
) -> AgentState:
    """Apply deterministic risk-control check to final response text."""

    forbidden_fragments = detect_forbidden_commitments(state)

    if not forbidden_fragments:
        return state

    risk_reasons = [
        f"forbidden_commitment_detected:{fragment}"
        for fragment in forbidden_fragments
    ]

    state["risk_triggered"] = True
    state["risk_reasons"] = _merge_text_lists(
        _list_of_text(state.get("risk_reasons")),
        risk_reasons,
    )
    state["handoff_required"] = True
    state["human_handoff"] = True
    state["final_response"] = (
        "当前回答命中风险控制规则，不能自动给出该类承诺，"
        "请转人工进一步确认。"
    )

    return state


def detect_forbidden_commitments(
    state: AgentState,
) -> list[str]:
    """Detect forbidden commitment fragments in response fields."""

    texts = [
        state.get("answer_text"),
        state.get("final_response"),
    ]

    joined_text = "\n".join(
        str(text)
        for text in texts
        if text is not None
    )

    return [
        fragment
        for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS
        if fragment in joined_text
    ]


def state_to_response_payload(
    state: AgentState,
) -> dict[str, Any]:
    """Convert AgentState to a serializable API-like response payload."""

    final_response = state.get("final_response")
    answer_text = state.get("answer_text")

    return {
        "session_id": state.get("session_id"),
        "conversation_id": state.get("conversation_id"),
        "selected_module": state.get("selected_module"),
        "route_status": state.get("route_status"),
        "route_confidence": state.get("route_confidence"),
        "parse_status": state.get("parse_status"),
        "handler_status": state.get("handler_status"),
        "answer_text": answer_text,
        "final_response": final_response,
        "handoff_required": state.get("handoff_required", False),
        "human_handoff": state.get("human_handoff", False),
        "handoff_ticket_id": state.get("handoff_ticket_id"),
        "handoff_ticket_no": state.get("handoff_ticket_no"),
        "source_references": state.get("source_references", []),
        "module_payload": state.get("module_payload"),
        "retrieved_chunks": state.get("retrieved_chunks", []),
        "risk_triggered": state.get("risk_triggered", False),
        "risk_reasons": state.get("risk_reasons", []),
        "user_message_id": state.get("user_message_id"),
        "assistant_message_id": state.get("assistant_message_id"),
        "warnings": state.get("warnings", []),
        "errors": state.get("errors", []),
        "metadata": state.get("metadata", {}),
    }


def _normalize_text(value: str) -> str:
    """Normalize user text for state-level tracking."""

    return (
        value.strip()
        .replace("Ｘ", "X")
        .replace("×", "X")
        .replace("＊", "*")
        .upper()
    )


def _optional_clean_text(value: str | None) -> str | None:
    """Return stripped text or None."""

    if value is None:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    return cleaned


def _optional_text(
    value: object,
    *,
    fallback: object | None = None,
) -> str | None:
    """Return optional text."""

    actual_value = fallback if value is None else value

    if actual_value is None:
        return None

    return str(actual_value)


def _optional_int(
    value: object,
    *,
    fallback: object | None = None,
) -> int | None:
    """Return optional int."""

    actual_value = fallback if value is None else value

    if actual_value is None:
        return None

    if isinstance(actual_value, bool):
        return None

    if isinstance(actual_value, int):
        return actual_value

    return int(str(actual_value))


def _optional_float(value: object) -> float | None:
    """Return optional float."""

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int | float):
        return float(value)

    return float(str(value))


def _bool_value(value: object) -> bool:
    """Return bool from unknown value."""

    if isinstance(value, bool):
        return value

    return False


def _list_of_text(value: object) -> list[str]:
    """Return list[str] from unknown value."""

    if not isinstance(value, list):
        return []

    return [str(item) for item in value]


def _list_of_dict(value: object) -> list[dict[str, Any]]:
    """Return list[dict[str, Any]] from unknown value."""

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


def _optional_dict(value: object) -> dict[str, Any] | None:
    """Return optional dict from unknown value."""

    if value is None:
        return None

    if not isinstance(value, dict):
        return None

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _merge_text_lists(
    left: list[str],
    right: list[str],
) -> list[str]:
    """Merge two text lists while preserving order."""

    result = list(left)

    for item in right:
        if item not in result:
            result.append(item)

    return result