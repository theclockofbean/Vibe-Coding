# ruff: noqa: E402,I001
"""Check quality workflow with real LLM rendering.

This check calls the real OpenAI-compatible LLM API only when real API env vars
are configured and the API key is not a placeholder.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
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


@dataclass(frozen=True)
class QualitySmokeCase:
    """One quality real LLM smoke case."""

    case_id: str
    user_text: str
    expected_contains: tuple[str, ...]
    expected_excludes: tuple[str, ...] = FORBIDDEN_COMMITMENT_FRAGMENTS


QUALITY_SMOKE_CASES: Final[tuple[QualitySmokeCase, ...]] = (
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_001",
        user_text="SKU001 这款铝合金的质量怎么样？",
        expected_contains=("SKU001", "铝合金"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_002",
        user_text="SKU001 从质量资料角度看，材质是不是铝合金6061？",
        expected_contains=("SKU001", "铝合金6061"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_003",
        user_text="SKU001 表面处理是什么？从质量资料角度怎么理解？",
        expected_contains=("SKU001", "阳极氧化"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_004",
        user_text="SKU001 从质量资料角度看，阳极氧化黑色有什么说明？",
        expected_contains=("SKU001", "阳极氧化"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_005",
        user_text="SKU001 从质量资料角度说明这个换挡球头的材质和表面处理",
        expected_contains=("SKU001", "参考来源"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_006",
        user_text="SKU001 有没有检测记录可以证明质量？",
        expected_contains=("SKU001", "人工确认"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_007",
        user_text="SKU001 从材料质量说明角度看，这款适合做轻量化零件吗？",
        expected_contains=("SKU001", "铝合金"),
    ),
    QualitySmokeCase(
        case_id="TC_QUAL_SMOKE_008",
        user_text="SKU001 材料和外观处理能给我一个安全说明吗？",
        expected_contains=("SKU001", "参考来源"),
    ),
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
    """Run one workflow case.

    Quality smoke cases force the low-confidence LLM intent classifier so this
    script verifies the quality rendering path instead of being intercepted by
    spec/material lookup routing.
    """

    initial_state: AgentState = {
        "session_id": session_id,
        "channel": "quality_real_llm_rendering_check",
        "user_id": "quality-real-llm-rendering-check-user",
        "user_text": user_text,
        "metadata": {
            "force_llm_intent_classifier": True,
        },
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


def check_quality_real_llm_rendering() -> bool:
    """Check quality rendering with real LLM."""

    print("=" * 80)
    print("checking quality real LLM rendering")

    if not real_api_env_ready():
        print("quality real LLM rendering skipped: env missing or placeholder")
        return True

    results: list[bool] = []

    with patched_env(
        {
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
            "AGENT_RENDER_FORCE_ERROR": "0",
            "LLM_INTENT_CLASSIFIER_ENABLED": "1",
        },
        preserve_existing_llm_env=True,
    ):
        for index, case in enumerate(QUALITY_SMOKE_CASES, start=1):
            session_id = f"quality-real-llm-rendering-{index:02d}"
            before_counts = count_db_side_effects(session_id=session_id)

            state = run_workflow_case(
                session_id=session_id,
                user_text=case.user_text,
            )

            after_counts = count_db_side_effects(session_id=session_id)

            passed = check_case_result(
                case=case,
                state=state,
                before_counts=before_counts,
                after_counts=after_counts,
            )

            results.append(passed)

    print("=" * 80)
    print("quality real LLM rendering case summary")

    for case, passed in zip(QUALITY_SMOKE_CASES, results, strict=True):
        status = "PASSED" if passed else "FAILED"
        print(f"{status:<8} {case.case_id} {case.user_text}")

    return all(results)


def check_case_result(
    *,
    case: QualitySmokeCase,
    state: AgentState,
    before_counts: tuple[int, int],
    after_counts: tuple[int, int],
) -> bool:
    """Check one quality case result."""

    print("=" * 80)
    print(f"checking {case.case_id}: {case.user_text}")

    metadata = _dict_value(state.get("metadata"))
    llm_response = _dict_value(state.get("llm_response"))
    render_output = _dict_value(state.get("render_output"))
    final_response = str(state.get("final_response") or "")
    response_sources = _list_of_dicts(state.get("response_sources"))

    pprint(
        {
            "case_id": case.case_id,
            "final_response": final_response,
            "metadata": metadata,
            "llm_response": llm_response,
            "response_sources": response_sources,
        }
    )

    source_types = {
        str(source.get("source_type"))
        for source in response_sources
    }

    expected_contains_ok = all(
        fragment in final_response
        for fragment in case.expected_contains
    )

    expected_excludes_ok = all(
        fragment not in final_response
        for fragment in case.expected_excludes
    )

    llm_output = str(state.get("llm_output") or "")

    llm_output_excludes_ok = all(
        fragment not in llm_output
        for fragment in case.expected_excludes
    )

    checks = [
        state.get("selected_module") == "quality",
        metadata.get("llm_used") is True,
        metadata.get("llm_real_api_enabled") is True,
        metadata.get("llm_provider") == os.getenv("LLM_PROVIDER"),
        metadata.get("llm_model") == os.getenv("LLM_MODEL"),
        llm_response.get("error") is None,
        llm_response.get("is_safe") is True,
        render_output.get("used_llm_output") is True,
        state.get("render_used_llm_output") is True,
        state.get("is_grounded_response") is True,
        bool(final_response.strip()),
        "参考来源" in final_response,
        "rag_chunk" in source_types,
        "business_rule" in source_types,
        expected_contains_ok,
        expected_excludes_ok,
        llm_output_excludes_ok,
        before_counts == after_counts,
    ]

    if not all(checks):
        print("case failed checks:")
        print(
            {
                "selected_module": state.get("selected_module"),
                "llm_used": metadata.get("llm_used"),
                "llm_real_api_enabled": metadata.get("llm_real_api_enabled"),
                "llm_error": llm_response.get("error"),
                "llm_is_safe": llm_response.get("is_safe"),
                "render_used_llm_output": state.get("render_used_llm_output"),
                "is_grounded_response": state.get("is_grounded_response"),
                "expected_contains_ok": expected_contains_ok,
                "expected_excludes_ok": expected_excludes_ok,
                "llm_output_excludes_ok": llm_output_excludes_ok,
                "db_side_effects_ok": before_counts == after_counts,
                "source_types": sorted(source_types),
            }
        )

    return all(checks)


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


def main() -> int:
    """Run quality real LLM rendering check."""

    reset_seed_and_qdrant_points()

    passed = check_quality_real_llm_rendering()

    print("=" * 80)

    if not passed:
        print("quality real LLM rendering check failed")
        return 1

    print("quality real LLM rendering check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())