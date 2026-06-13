# ruff: noqa: E402,I001
"""Check workflow LLMNode integration.

This script verifies LLMNode writes LLM metadata without modifying final_response
or creating database side effects.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import AgentState
from app.agent.workflow import run_agent_workflow
from app.core.database import get_session_factory
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.product_repository import ProductRepository
from scripts.create_qdrant_collection import main as create_qdrant_collection_main
from scripts.seed_rag_knowledge_chunks import cleanup_existing_seed_rows, seed_chunks
from scripts.upsert_seed_chunks_to_qdrant import upsert_seed_chunks


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


def reset_seed_and_qdrant_points() -> None:
    """Reset seed rows and qdrant points."""

    cleanup_existing_seed_rows()
    seed_chunks()

    create_result = create_qdrant_collection_main()

    if create_result != 0:
        raise RuntimeError("failed to create qdrant collection")

    upsert_seed_chunks()


def count_conversation_messages(
    *,
    session_id: str,
) -> int:
    """Count conversation messages."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM conversation_messages
                WHERE session_id = :session_id;
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    return int(result)


def count_handoff_tickets(
    *,
    session_id: str,
) -> int:
    """Count handoff tickets."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM handoff_tickets
                WHERE session_id = :session_id;
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    return int(result)


def run_workflow_case(
    *,
    session_id: str,
    user_text: str,
) -> AgentState:
    """Run workflow case."""

    initial_state: AgentState = {
        "session_id": session_id,
        "channel": "workflow_llm_node_check",
        "user_id": "workflow-llm-node-check-user",
        "user_text": user_text,
    }

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        conversation_repository = ConversationRepository(session)

        result_state = run_agent_workflow(
            initial_state=initial_state,
            product_repository=product_repository,
            conversation_repository=conversation_repository,
            limit=5,
        )

    return result_state


def check_llm_node_success() -> bool:
    """Check LLMNode success path."""

    print("=" * 80)
    print("checking workflow LLMNode success path")

    os.environ.pop("AGENT_LLM_FORCE_ERROR", None)
    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"

    session_id = "workflow-llm-node-success-session"

    before_message_count = count_conversation_messages(session_id=session_id)
    before_ticket_count = count_handoff_tickets(session_id=session_id)

    state = run_workflow_case(
        session_id=session_id,
        user_text="SKU001 阳极氧化 表面处理 材质说明",
    )

    after_message_count = count_conversation_messages(session_id=session_id)
    after_ticket_count = count_handoff_tickets(session_id=session_id)

    metadata = _dict_value(state.get("metadata"))
    llm_request = _dict_value(state.get("llm_request"))
    llm_response = _dict_value(state.get("llm_response"))

    pprint(state)

    checks = [
        "llm" in _as_text_list(metadata.get("visited_nodes")),
        metadata.get("llm_enabled") is True,
        metadata.get("llm_used") is True,
        metadata.get("llm_provider") == "local",
        metadata.get("llm_model") == "rule-based-llm-v1",
        metadata.get("llm_task_type") == "summarize_evidence",
        metadata.get("llm_is_safe") is True,
        metadata.get("llm_needs_handoff") is False,
        llm_request.get("task_type") == "summarize_evidence",
        llm_response.get("metadata", {}).get("final_response_allowed") is False,
        state.get("final_response") == state.get("answer_text"),
        before_message_count == after_message_count,
        before_ticket_count == after_ticket_count,
    ]

    return all(checks)


def check_llm_node_handoff_task() -> bool:
    """Check handoff response uses draft_handoff_note task."""

    print("=" * 80)
    print("checking workflow LLMNode handoff task")

    os.environ.pop("AGENT_LLM_FORCE_ERROR", None)
    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"

    state = run_workflow_case(
        session_id="workflow-llm-node-handoff-session",
        user_text="SKU001 多少钱 报价 价格边界",
    )

    metadata = _dict_value(state.get("metadata"))
    llm_response = _dict_value(state.get("llm_response"))

    pprint(state)

    checks = [
        state.get("handoff_required") is True,
        metadata.get("llm_task_type") == "draft_handoff_note",
        metadata.get("llm_used") is True,
        llm_response.get("is_safe") is True,
        state.get("final_response") == state.get("answer_text"),
    ]

    return all(checks)


def check_llm_node_error_fallback() -> bool:
    """Check LLMNode error does not fail workflow."""

    print("=" * 80)
    print("checking workflow LLMNode error fallback")

    old_force_error = os.environ.get("AGENT_LLM_FORCE_ERROR")
    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"
    os.environ["AGENT_LLM_FORCE_ERROR"] = "1"

    try:
        state = run_workflow_case(
            session_id="workflow-llm-node-error-session",
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )
    finally:
        if old_force_error is None:
            os.environ.pop("AGENT_LLM_FORCE_ERROR", None)
        else:
            os.environ["AGENT_LLM_FORCE_ERROR"] = old_force_error

    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        "llm" in _as_text_list(metadata.get("visited_nodes")),
        metadata.get("llm_used") is False,
        bool(metadata.get("llm_error")),
        state.get("llm_used") is False,
        bool(state.get("llm_error")),
        state.get("final_response") == state.get("answer_text"),
    ]

    return all(checks)


def check_llm_node_disabled() -> bool:
    """Check disabled LLMNode path."""

    print("=" * 80)
    print("checking workflow LLMNode disabled path")

    old_enabled = os.environ.get("AGENT_LLM_NODE_ENABLED")
    os.environ["AGENT_LLM_NODE_ENABLED"] = "0"

    try:
        state = run_workflow_case(
            session_id="workflow-llm-node-disabled-session",
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )
    finally:
        if old_enabled is None:
            os.environ.pop("AGENT_LLM_NODE_ENABLED", None)
        else:
            os.environ["AGENT_LLM_NODE_ENABLED"] = old_enabled

    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        "llm" in _as_text_list(metadata.get("visited_nodes")),
        metadata.get("llm_enabled") is False,
        metadata.get("llm_used") is False,
        state.get("llm_used") is False,
        state.get("final_response") == state.get("answer_text"),
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check LLMNode outputs contain no forbidden commitment fragments."""

    print("=" * 80)
    print("checking no forbidden commitment fragments")

    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"
    os.environ.pop("AGENT_LLM_FORCE_ERROR", None)

    state = run_workflow_case(
        session_id="workflow-llm-node-forbidden-session",
        user_text="SKU001 材质说明",
    )

    llm_output = str(state.get("llm_output") or "")

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in llm_output:
            print(f"failed: forbidden fragment in llm_output: {fragment}")
            return False

    return True


def _dict_value(
    value: object,
) -> dict[str, Any]:
    """Return dict value."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _as_text_list(
    value: object,
) -> list[str]:
    """Return text list."""

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
    ]


def main() -> int:
    """Run workflow LLMNode checks."""

    reset_seed_and_qdrant_points()

    results = [
        check_llm_node_success(),
        check_llm_node_handoff_task(),
        check_llm_node_error_fallback(),
        check_llm_node_disabled(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("workflow llm node check failed")
        return 1

    print("workflow llm node check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())