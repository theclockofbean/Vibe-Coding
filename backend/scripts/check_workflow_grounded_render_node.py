# ruff: noqa: E402,I001
"""Check workflow Grounded RenderNode integration."""

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
        "channel": "workflow_grounded_render_check",
        "user_id": "workflow-grounded-render-check-user",
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


def check_grounded_spec_quality_render() -> bool:
    """Check grounded render for spec/quality-like query."""

    print("=" * 80)
    print("checking grounded spec quality render")

    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"
    os.environ.pop("AGENT_LLM_FORCE_ERROR", None)
    os.environ.pop("AGENT_RENDER_FORCE_ERROR", None)

    session_id = "workflow-grounded-render-spec-session"

    before_message_count = count_conversation_messages(session_id=session_id)
    before_ticket_count = count_handoff_tickets(session_id=session_id)

    state = run_workflow_case(
        session_id=session_id,
        user_text="SKU001 阳极氧化 表面处理 材质说明",
    )

    after_message_count = count_conversation_messages(session_id=session_id)
    after_ticket_count = count_handoff_tickets(session_id=session_id)

    metadata = _dict_value(state.get("metadata"))
    response_sources = _list_of_dicts(state.get("response_sources"))
    source_types = {
        str(source.get("source_type"))
        for source in response_sources
    }

    pprint(state)

    checks = [
        "render" in _as_text_list(metadata.get("visited_nodes")),
        metadata.get("render_mode") == "grounded",
        metadata.get("render_is_grounded") is True,
        state.get("is_grounded_response") is True,
        "查到 SKU001" in str(state.get("final_response")),
        "补充说明" in str(state.get("final_response")),
        "参考来源" in str(state.get("final_response")),
        len(response_sources) >= 2,
        "products" in source_types,
        "rag_chunk" in source_types,
        "business_rule" in source_types,
        before_message_count == after_message_count,
        before_ticket_count == after_ticket_count,
    ]

    return all(checks)


def check_grounded_price_render() -> bool:
    """Check grounded render for price query."""

    print("=" * 80)
    print("checking grounded price render")

    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"
    os.environ.pop("AGENT_LLM_FORCE_ERROR", None)
    os.environ.pop("AGENT_RENDER_FORCE_ERROR", None)

    state = run_workflow_case(
        session_id="workflow-grounded-render-price-session",
        user_text="SKU001 多少钱 报价 价格边界",
    )

    metadata = _dict_value(state.get("metadata"))
    final_response = str(state.get("final_response") or "")
    response_sources = _list_of_dicts(state.get("response_sources"))

    pprint(state)

    checks = [
        state.get("handoff_required") is True,
        state.get("human_handoff") is True,
        metadata.get("render_mode") == "grounded",
        metadata.get("render_safety_blocked") is False,
        "不能直接给出报价" in final_response,
        "正式价格表" in final_response,
        "99 元" not in final_response,
        "￥" not in final_response,
        len(response_sources) >= 2,
    ]

    return all(checks)


def check_render_node_error_fallback() -> bool:
    """Check forced render error falls back safely."""

    print("=" * 80)
    print("checking grounded render node error fallback")

    old_force_error = os.environ.get("AGENT_RENDER_FORCE_ERROR")
    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"
    os.environ["AGENT_RENDER_FORCE_ERROR"] = "1"

    try:
        state = run_workflow_case(
            session_id="workflow-grounded-render-error-session",
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )
    finally:
        if old_force_error is None:
            os.environ.pop("AGENT_RENDER_FORCE_ERROR", None)
        else:
            os.environ["AGENT_RENDER_FORCE_ERROR"] = old_force_error

    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        metadata.get("render_mode") == "workflow_render_fallback",
        metadata.get("render_is_grounded") is False,
        bool(metadata.get("render_fallback_reason")),
        state.get("is_grounded_response") is False,
        "查到 SKU001" in str(state.get("final_response")),
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check final response has no forbidden commitment fragments."""

    print("=" * 80)
    print("checking no forbidden fragments in final_response")

    os.environ["AGENT_LLM_NODE_ENABLED"] = "1"
    os.environ.pop("AGENT_RENDER_FORCE_ERROR", None)

    state = run_workflow_case(
        session_id="workflow-grounded-render-forbidden-session",
        user_text="SKU001 阳极氧化 表面处理 材质说明",
    )

    final_response = str(state.get("final_response") or "")

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in final_response:
            print(f"failed: forbidden fragment detected: {fragment}")
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


def _list_of_dicts(
    value: object,
) -> list[dict[str, Any]]:
    """Return list of dicts."""

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
    """Run workflow grounded render checks."""

    reset_seed_and_qdrant_points()

    results = [
        check_grounded_spec_quality_render(),
        check_grounded_price_render(),
        check_render_node_error_fallback(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("workflow grounded render node check failed")
        return 1

    print("workflow grounded render node check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())