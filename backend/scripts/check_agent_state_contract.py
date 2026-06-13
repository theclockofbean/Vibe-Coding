# ruff: noqa: E402,I001
"""Check AgentState contract."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import (
    apply_conversation_context,
    apply_retrieved_chunks,
    apply_risk_control,
    apply_unified_payload,
    create_initial_agent_state,
    detect_forbidden_commitments,
    state_to_response_payload,
)


def build_spec_payload() -> dict[str, Any]:
    """Build a successful spec payload."""

    return {
        "session_id": "session-state-test",
        "conversation_id": 101,
        "selected_module": "spec",
        "route_status": "routed",
        "route_confidence": 0.75,
        "candidate_modules": ["spec"],
        "matched_signals": ["螺纹"],
        "matched_sku": "SKU001",
        "parse_status": "parsed",
        "handler_status": "success",
        "answer_text": "查到 SKU001：螺纹规格为 M8×1.25。",
        "handoff_required": False,
        "handoff_ticket_id": None,
        "handoff_ticket_no": None,
        "source_references": [
            {
                "source_type": "database_table",
                "source_name": "products",
                "reference_id": "SKU001",
            }
        ],
        "module_payload": {
            "selected_module": "spec",
            "handler_status": "success",
        },
        "user_message_id": 201,
        "assistant_message_id": 202,
        "warnings": [],
        "errors": [],
    }


def build_handoff_payload() -> dict[str, Any]:
    """Build a handoff payload."""

    return {
        "session_id": "session-state-test",
        "conversation_id": 101,
        "selected_module": "price",
        "route_status": "routed",
        "route_confidence": 0.75,
        "candidate_modules": ["price"],
        "matched_signals": ["多少钱"],
        "matched_sku": "SKU001",
        "parse_status": "parsed",
        "handler_status": "handoff",
        "answer_text": (
            "查到 SKU001。当前系统尚未接入正式价格表，"
            "不能直接给出报价，请转人工确认。"
        ),
        "handoff_required": True,
        "handoff_ticket_id": 301,
        "handoff_ticket_no": "HT-STATE-301",
        "source_references": [],
        "module_payload": {
            "selected_module": "price",
            "handler_status": "handoff",
        },
        "user_message_id": 401,
        "assistant_message_id": 402,
        "warnings": [],
        "errors": [],
    }


def check_initial_state() -> bool:
    """Check initial AgentState defaults."""

    print("=" * 80)
    print("checking initial state")

    state = create_initial_agent_state(
        session_id=None,
        channel="local_test",
        user_id="user-state-test",
        user_text=" sku001 螺纹是多少 ",
    )

    pprint(state)

    checks = [
        state["session_id"] is None,
        state["channel"] == "local_test",
        state["user_id"] == "user-state-test",
        state["user_text"] == " sku001 螺纹是多少 ",
        state["normalized_text"] == "SKU001 螺纹是多少",
        state["conversation_history"] == [],
        state["candidate_modules"] == [],
        state["matched_signals"] == [],
        state["retrieved_chunks"] == [],
        state["source_references"] == [],
        state["module_payload"] is None,
        state["answer_text"] is None,
        state["final_response"] is None,
        state["handoff_required"] is False,
        state["human_handoff"] is False,
        state["risk_triggered"] is False,
        state["risk_reasons"] == [],
        state["warnings"] == [],
        state["errors"] == [],
    ]

    return all(checks)


def check_conversation_context() -> bool:
    """Check conversation context mapping."""

    print("=" * 80)
    print("checking conversation context")

    state = create_initial_agent_state(
        session_id="session-state-test",
        channel="local_test",
        user_id="user-state-test",
        user_text="SKU001 多少钱",
    )

    state = apply_conversation_context(
        state,
        conversation_id=101,
        conversation_history=[
            {
                "role": "user",
                "content": "SKU001 螺纹是多少",
            },
            {
                "role": "assistant",
                "content": "查到 SKU001：螺纹规格为 M8×1.25。",
            },
        ],
    )

    pprint(state)

    checks = [
        state["conversation_id"] == 101,
        len(state["conversation_history"]) == 2,
        state["conversation_history"][0]["role"] == "user",
        state["conversation_history"][1]["role"] == "assistant",
    ]

    return all(checks)


def check_unified_payload_mapping() -> bool:
    """Check mapping from current unified payload."""

    print("=" * 80)
    print("checking unified payload mapping")

    state = create_initial_agent_state(
        session_id=None,
        channel="local_test",
        user_id="user-state-test",
        user_text="SKU001 螺纹是多少",
    )

    state = apply_unified_payload(
        state,
        payload=build_spec_payload(),
    )

    response_payload = state_to_response_payload(state)

    pprint(state)
    pprint(response_payload)

    checks = [
        state["session_id"] == "session-state-test",
        state["conversation_id"] == 101,
        state["selected_module"] == "spec",
        state["route_status"] == "routed",
        state["route_confidence"] == 0.75,
        state["candidate_modules"] == ["spec"],
        state["matched_signals"] == ["螺纹"],
        state["matched_sku"] == "SKU001",
        state["parse_status"] == "parsed",
        state["handler_status"] == "success",
        state["handoff_required"] is False,
        state["human_handoff"] is False,
        state["source_references"][0]["reference_id"] == "SKU001",
        state["module_payload"] is not None,
        state["user_message_id"] == 201,
        state["assistant_message_id"] == 202,
        response_payload["selected_module"] == "spec",
        response_payload["handoff_required"] is False,
    ]

    return all(checks)


def check_handoff_mapping() -> bool:
    """Check handoff fields mapping."""

    print("=" * 80)
    print("checking handoff mapping")

    state = create_initial_agent_state(
        session_id="session-state-test",
        channel="local_test",
        user_id="user-state-test",
        user_text="SKU001 多少钱",
    )

    state = apply_unified_payload(
        state,
        payload=build_handoff_payload(),
    )

    response_payload = state_to_response_payload(state)

    pprint(state)
    pprint(response_payload)

    checks = [
        state["selected_module"] == "price",
        state["handler_status"] == "handoff",
        state["handoff_required"] is True,
        state["human_handoff"] is True,
        state["handoff_ticket_id"] == 301,
        state["handoff_ticket_no"] == "HT-STATE-301",
        response_payload["handoff_ticket_id"] == 301,
        response_payload["handoff_ticket_no"] == "HT-STATE-301",
    ]

    return all(checks)


def check_retrieved_chunks() -> bool:
    """Check RAG chunk attachment."""

    print("=" * 80)
    print("checking retrieved chunks")

    state = create_initial_agent_state(
        session_id="session-state-test",
        channel="local_test",
        user_id="user-state-test",
        user_text="SKU001 表面处理是什么",
    )

    state = apply_retrieved_chunks(
        state,
        retrieved_chunks=[
            {
                "collection": "quality_kb",
                "chunk_id": "quality-001",
                "title": "铝合金表面处理说明",
                "content": "阳极氧化是一类常见表面处理。",
                "score": 0.82,
            }
        ],
    )

    pprint(state)

    checks = [
        len(state["retrieved_chunks"]) == 1,
        state["retrieved_chunks"][0]["collection"] == "quality_kb",
        state["retrieved_chunks"][0]["chunk_id"] == "quality-001",
    ]

    return all(checks)


def check_risk_control() -> bool:
    """Check deterministic risk control boundary."""

    print("=" * 80)
    print("checking risk control")

    state = create_initial_agent_state(
        session_id="session-state-test",
        channel="local_test",
        user_id="user-state-test",
        user_text="SKU001 会不会生锈",
    )

    state["answer_text"] = "这个产品保证不生锈。"
    state["final_response"] = "这个产品保证不生锈。"

    detected = detect_forbidden_commitments(state)
    state = apply_risk_control(state)
    response_payload = state_to_response_payload(state)

    pprint(state)
    pprint(response_payload)

    checks = [
        "保证不生锈" in detected,
        state["risk_triggered"] is True,
        state["handoff_required"] is True,
        state["human_handoff"] is True,
        bool(state["risk_reasons"]),
        "保证不生锈" not in str(response_payload["final_response"]),
        "转人工" in str(response_payload["final_response"]),
    ]

    return all(checks)


def main() -> int:
    """Run AgentState contract checks."""

    results = [
        check_initial_state(),
        check_conversation_context(),
        check_unified_payload_mapping(),
        check_handoff_mapping(),
        check_retrieved_chunks(),
        check_risk_control(),
    ]

    print("=" * 80)

    if not all(results):
        print("agent state contract check failed")
        return 1

    print("agent state contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())