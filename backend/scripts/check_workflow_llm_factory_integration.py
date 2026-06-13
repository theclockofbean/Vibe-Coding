# ruff: noqa: E402,I001
"""Check workflow LLMClientFactory integration."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from pprint import pprint
from typing import Any, Final
from collections.abc import Iterator

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


ENV_KEYS: Final[tuple[str, ...]] = (
    "AGENT_LLM_NODE_ENABLED",
    "AGENT_LLM_FORCE_ERROR",
    "AGENT_RENDER_FORCE_ERROR",
    "LLM_ENABLE_REAL_API",
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
)


PLACEHOLDER_API_KEYS: Final[set[str]] = {
    "",
    "test",
    "testapi",
    "test_api",
    "your_api_key",
    "your-api-key",
    "replace_me",
    "placeholder",
}


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


def run_workflow_case(
    *,
    session_id: str,
    user_text: str,
) -> AgentState:
    """Run workflow case."""

    initial_state: AgentState = {
        "session_id": session_id,
        "channel": "workflow_llm_factory_check",
        "user_id": "workflow-llm-factory-check-user",
        "user_text": user_text,
    }

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session)
        conversation_repository = ConversationRepository(session)

        return run_agent_workflow(
            initial_state=initial_state,
            product_repository=product_repository,
            conversation_repository=conversation_repository,
            limit=5,
        )


def count_db_side_effects(
    *,
    session_id: str,
) -> tuple[int, int]:
    """Count conversation messages and handoff tickets."""

    session_factory = get_session_factory()

    with session_factory() as session:
        message_count = session.execute(
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

        ticket_count = session.execute(
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

    return int(message_count), int(ticket_count)


def check_workflow_factory_rule_based_default() -> bool:
    """Check workflow uses RuleBased fallback when real API is disabled."""

    print("=" * 80)
    print("checking workflow LLM factory default rule-based mode")

    session_id = "workflow-llm-factory-rule-based-session"
    before_counts = count_db_side_effects(session_id=session_id)

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        state = run_workflow_case(
            session_id=session_id,
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )

    after_counts = count_db_side_effects(session_id=session_id)
    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        metadata.get("llm_used") is True,
        metadata.get("llm_provider") == "local",
        metadata.get("llm_model") == "rule-based-llm-v1",
        metadata.get("llm_real_api_enabled") is False,
        metadata.get("llm_factory_fallback_reason") == "real_api_disabled",
        state.get("is_grounded_response") is True,
        "查到 SKU001" in str(state.get("final_response")),
        before_counts == after_counts,
    ]

    return all(checks)


def check_workflow_factory_incomplete_config_fallback() -> bool:
    """Check incomplete real API config falls back to RuleBased client."""

    print("=" * 80)
    print("checking workflow LLM factory incomplete config fallback")

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_ENABLE_REAL_API": "1",
            "LLM_PROVIDER": "deepseek",
            "LLM_BASE_URL": "https://api.deepseek.com",
            "LLM_API_KEY": "",
            "LLM_MODEL": "deepseek-v4-flash",
        }
    ):
        state = run_workflow_case(
            session_id="workflow-llm-factory-incomplete-session",
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )

    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        metadata.get("llm_used") is True,
        metadata.get("llm_provider") == "local",
        metadata.get("llm_model") == "rule-based-llm-v1",
        metadata.get("llm_real_api_enabled") is False,
        metadata.get("llm_factory_fallback_reason")
        == "real_api_config_incomplete",
        "real LLM API config is incomplete"
        in _as_text_list(metadata.get("llm_factory_warnings")),
        state.get("is_grounded_response") is True,
    ]

    return all(checks)


def check_workflow_factory_real_api_if_configured() -> bool:
    """Check real API workflow path when real API env vars are configured."""

    print("=" * 80)
    print("checking workflow LLM factory real API path if configured")

    if not _real_api_env_ready():
        print("real API workflow check skipped: env is missing or placeholder")
        return True

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
        },
        preserve_existing_llm_env=True,
    ):
        state = run_workflow_case(
            session_id="workflow-llm-factory-real-api-session",
            user_text="SKU001 这款铝合金的质量怎么样？",
        )

    metadata = _dict_value(state.get("metadata"))
    llm_response = _dict_value(state.get("llm_response"))
    final_response = str(state.get("final_response") or "")

    pprint(state)

    checks = [
        metadata.get("llm_used") is True,
        metadata.get("llm_provider") == os.getenv("LLM_PROVIDER"),
        metadata.get("llm_model") == os.getenv("LLM_MODEL"),
        metadata.get("llm_real_api_enabled") is True,
        llm_response.get("error") is None,
        llm_response.get("is_safe") is True,
        state.get("is_grounded_response") is True,
        bool(final_response.strip()),
        "参考来源" in final_response,
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check workflow final response and LLM output contain no forbidden fragments."""

    print("=" * 80)
    print("checking no forbidden commitment fragments")

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        state = run_workflow_case(
            session_id="workflow-llm-factory-forbidden-session",
            user_text="SKU001 阳极氧化 表面处理 材质说明",
        )

    final_response = str(state.get("final_response") or "")
    llm_output = str(state.get("llm_output") or "")
    llm_request = _dict_value(state.get("llm_request"))

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in final_response:
            print(f"failed: forbidden fragment in final_response: {fragment}")
            return False

        if fragment in llm_output:
            print(f"failed: forbidden fragment in llm_output: {fragment}")
            return False

        if fragment in str(llm_request):
            print(f"failed: forbidden fragment stored in llm_request: {fragment}")
            return False

    return True


def _real_api_env_ready() -> bool:
    """Return whether real API env vars are ready."""

    enabled = os.getenv("LLM_ENABLE_REAL_API", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    provider = os.getenv("LLM_PROVIDER", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    return (
        enabled
        and bool(provider)
        and bool(base_url)
        and bool(model)
        and api_key.lower() not in PLACEHOLDER_API_KEYS
    )


@contextmanager
def patched_env(
    values: dict[str, str],
    *,
    preserve_existing_llm_env: bool = False,
) -> Iterator[None]:
    """Temporarily patch env vars."""

    old_values: dict[str, str | None] = {
        key: os.environ.get(key)
        for key in ENV_KEYS
    }

    try:
        if not preserve_existing_llm_env:
            for key in ENV_KEYS:
                os.environ.pop(key, None)

        for key, value in values.items():
            os.environ[key] = value

        yield
    finally:
        for key in ENV_KEYS:
            old_value = old_values[key]

            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


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
        if str(item).strip()
    ]


def main() -> int:
    """Run workflow LLM factory integration checks."""

    reset_seed_and_qdrant_points()

    results = [
        check_workflow_factory_rule_based_default(),
        check_workflow_factory_incomplete_config_fallback(),
        check_workflow_factory_real_api_if_configured(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("workflow LLM factory integration check failed")
        return 1

    print("workflow LLM factory integration check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())