# ruff: noqa: E402,I001
"""Check Workflow IntentNode LLM fallback integration."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from pprint import pprint
from typing import Any, Final

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
    "LLM_INTENT_CLASSIFIER_ENABLED",
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
    metadata: dict[str, Any] | None = None,
) -> AgentState:
    """Run workflow case."""

    initial_state: AgentState = {
        "session_id": session_id,
        "channel": "workflow_llm_intent_fallback_check",
        "user_id": "workflow-llm-intent-fallback-check-user",
        "user_text": user_text,
    }

    if metadata:
        initial_state["metadata"] = metadata

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


def check_intent_classifier_disabled() -> bool:
    """Check IntentNode skips LLM classifier when disabled."""

    print("=" * 80)
    print("checking intent classifier disabled")

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_INTENT_CLASSIFIER_ENABLED": "0",
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        state = run_workflow_case(
            session_id="workflow-llm-intent-disabled-session",
            user_text="SKU001 这款铝合金的质量怎么样？",
        )

    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        metadata.get("llm_intent_classifier_enabled") is False,
        metadata.get("llm_intent_classifier_used") is False,
        metadata.get("llm_intent_fallback_reason")
        == "llm_intent_classifier_disabled",
        state.get("final_response") is not None,
    ]

    return all(checks)


def check_high_confidence_rule_based_skip() -> bool:
    """Check high-confidence rule-based route skips LLM classifier."""

    print("=" * 80)
    print("checking high confidence rule-based skip")

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_INTENT_CLASSIFIER_ENABLED": "1",
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        state = run_workflow_case(
            session_id="workflow-llm-intent-high-confidence-session",
            user_text="SKU001 螺纹规格是多少",
        )

    metadata = _dict_value(state.get("metadata"))

    pprint(state)

    checks = [
        metadata.get("llm_intent_classifier_used") is False,
        metadata.get("llm_intent_fallback_reason")
        == "rule_based_high_confidence",
        state.get("final_response") is not None,
    ]

    return all(checks)


def check_low_confidence_fallback_without_real_api() -> bool:
    """Check low confidence falls back safely when real API disabled."""

    print("=" * 80)
    print("checking low confidence fallback without real API")

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_INTENT_CLASSIFIER_ENABLED": "1",
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        state = run_workflow_case(
            session_id="workflow-llm-intent-no-real-api-session",
            user_text="这款铝合金质量怎么样",
            metadata={
                "force_llm_intent_classifier": True,
            },
        )

    metadata = _dict_value(state.get("metadata"))
    intent_result = _dict_value(metadata.get("llm_intent_result"))

    pprint(state)

    checks = [
        metadata.get("llm_intent_classifier_used") is False,
        metadata.get("llm_intent_applied") is True,
        intent_result.get("intent") == "quality",
        state.get("selected_module") == "quality",
        bool(metadata.get("llm_intent_fallback_reason")),
        state.get("final_response") is not None,
    ]

    return all(checks)


def check_low_confidence_real_api_if_configured() -> bool:
    """Check low confidence real API intent fallback when env is ready."""

    print("=" * 80)
    print("checking low confidence real API intent fallback if configured")

    if not real_api_env_ready():
        print("real API intent workflow check skipped: env missing or placeholder")
        return True

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_INTENT_CLASSIFIER_ENABLED": "1",
        },
        preserve_existing_llm_env=True,
    ):
        state = run_workflow_case(
            session_id="workflow-llm-intent-real-api-session",
            user_text="SKU001 这款铝合金的质量怎么样？会不会容易掉漆？",
            metadata={
                "force_llm_intent_classifier": True,
            },
        )

    metadata = _dict_value(state.get("metadata"))
    intent_result = _dict_value(metadata.get("llm_intent_result"))
    final_response = str(state.get("final_response") or "")

    pprint(state)

    checks = [
        metadata.get("llm_intent_classifier_used") is True,
        metadata.get("llm_intent_applied") is True,
        metadata.get("llm_intent_applied_intent") == "quality",
        intent_result.get("intent") == "quality",
        state.get("selected_module") == "quality",
        state.get("is_grounded_response") is True,
        "参考来源" in final_response,
    ]

    return all(checks)


def check_no_forbidden_fragments() -> bool:
    """Check final response and intent metadata do not store forbidden fragments."""

    print("=" * 80)
    print("checking no forbidden fragments")

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_INTENT_CLASSIFIER_ENABLED": "1",
            "LLM_ENABLE_REAL_API": "0",
            "LLM_PROVIDER": "rule_based",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
        }
    ):
        state = run_workflow_case(
            session_id="workflow-llm-intent-forbidden-session",
            user_text="SKU001 螺纹规格是多少",
        )

    final_response = str(state.get("final_response") or "")
    metadata = str(state.get("metadata") or {})

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in final_response:
            print(f"failed: forbidden fragment in final_response: {fragment}")
            return False

        if fragment in metadata:
            print(f"failed: forbidden fragment in metadata: {fragment}")
            return False

    return True


def real_api_env_ready() -> bool:
    """Return whether real API env vars are ready."""

    enabled = os.getenv("LLM_ENABLE_REAL_API", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    provider = os.getenv("LLM_PROVIDER", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()

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


def main() -> int:
    """Run workflow LLM intent fallback checks."""

    reset_seed_and_qdrant_points()

    results = [
        check_intent_classifier_disabled(),
        check_high_confidence_rule_based_skip(),
        check_low_confidence_fallback_without_real_api(),
        check_low_confidence_real_api_if_configured(),
        check_no_forbidden_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("workflow LLM intent fallback check failed")
        return 1

    print("workflow LLM intent fallback check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())