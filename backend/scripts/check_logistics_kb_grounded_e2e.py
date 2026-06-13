# ruff: noqa: E402,I001
"""Check real Logistics KB retrieval plus grounded final response."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import AgentState
from app.agent.workflow import build_agent_workflow
from app.core.database import get_session_factory
from app.repositories import ProductRepository


ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

TEST_CASES: Final[tuple[dict[str, str], ...]] = (
    {
        "case_id": "LOGISTICS_E2E_001",
        "query": "SKU001今天拍什么时候发货？",
    },
    {
        "case_id": "LOGISTICS_E2E_002",
        "query": "SKU001发浙江大概几天能到？",
    },
    {
        "case_id": "LOGISTICS_E2E_003",
        "query": "SKU001这个订单包邮吗？",
    },
    {
        "case_id": "LOGISTICS_E2E_004",
        "query": "偏远地区运费怎么确认？",
    },
    {
        "case_id": "LOGISTICS_E2E_005",
        "query": "物流损坏了是不是一定赔？",
    },
)

FORBIDDEN_RESPONSE_FRAGMENTS: Final[tuple[str, ...]] = (
    "一定包邮",
    "保证包邮",
    "今天一定发",
    "当天一定发",
    "明天一定到",
    "三天必到",
    "保证到货",
    "保证不延误",
    "固定运费",
    "运费就是",
    "一定赔",
    "一定补发",
    "退货运费一定我们出",
)


def check_logistics_kb_grounded_e2e() -> bool:
    """Check Logistics KB grounded E2E."""

    print("=" * 80)
    print("checking real Logistics KB grounded E2E")

    load_env_file(ENV_FILE)
    set_required_env()

    session_factory = get_session_factory()
    case_results: list[dict[str, Any]] = []
    errors: list[str] = []

    with session_factory() as session:
        product_repository = ProductRepository(session=session)

        workflow = build_agent_workflow(
            product_repository=product_repository,
            conversation_repository=None,
        )

        for case in TEST_CASES:
            result = run_one_case(
                workflow=workflow,
                case_id=case["case_id"],
                query=case["query"],
            )
            case_results.append(result)
            errors.extend(
                f"{case['case_id']}: {error}"
                for error in result["errors"]
            )

    safe_result = {
        "case_count": len(TEST_CASES),
        "results": case_results,
        "errors": errors,
    }

    serialized = json.dumps(safe_result, ensure_ascii=False)
    embedding_api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()

    if embedding_api_key and embedding_api_key in serialized:
        errors.append("EMBEDDING_API_KEY leaked into E2E check result")

    if llm_api_key and llm_api_key in serialized:
        errors.append("LLM_API_KEY leaked into E2E check result")

    pprint(safe_result)

    if errors:
        print("real Logistics KB grounded E2E check failed")
        return False

    print("real Logistics KB grounded E2E check passed")
    return True


def run_one_case(
    *,
    workflow: Any,
    case_id: str,
    query: str,
) -> dict[str, Any]:
    """Run one workflow case."""

    initial_state = cast(
        AgentState,
        {
            "current_message": query,
            "user_message": query,
            "user_text": query,
            "query": query,
            "intent": "logistics",
            "selected_module": "logistics",
            "candidate_modules": ["logistics"],
            "metadata": {
                "force_llm_intent_classifier": True,
                "test_case": case_id,
            },
        },
    )

    result_state = workflow.invoke(initial_state)

    metadata = ensure_dict(result_state.get("metadata"))
    retrieved_chunks = ensure_list(result_state.get("retrieved_chunks"))
    response_sources = ensure_list(result_state.get("response_sources"))
    final_response = str(
        result_state.get("final_response")
        or result_state.get("answer_text")
        or ""
    ).strip()

    case_errors: list[str] = []

    if metadata.get("real_logistics_kb_retriever_used") is not True:
        case_errors.append("real_logistics_kb_retriever_used must be true")

    if metadata.get("retrieval_source") != "real_logistics_kb":
        case_errors.append("retrieval_source must be real_logistics_kb")

    if metadata.get("retrieval_collection_name") != "logistics_kb_v1":
        case_errors.append("retrieval_collection_name must be logistics_kb_v1")

    if not retrieved_chunks:
        case_errors.append("retrieved_chunks is empty")

    if retrieved_chunks:
        top_chunk = ensure_dict(retrieved_chunks[0])

        if top_chunk.get("module") != "logistics":
            case_errors.append("top retrieved chunk module must be logistics")

        if top_chunk.get("collection_name") != "logistics_kb_v1":
            case_errors.append(
                "top retrieved chunk collection_name must be logistics_kb_v1"
            )

        if top_chunk.get("allow_answer_reference") is not True:
            case_errors.append(
                "top retrieved chunk allow_answer_reference must be true"
            )

        if top_chunk.get("allow_commitment_reference") is not False:
            case_errors.append(
                "top retrieved chunk allow_commitment_reference must be false"
            )

    if not final_response:
        case_errors.append("final_response is empty")

    for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
        if fragment in final_response:
            case_errors.append(f"final_response contains forbidden fragment: {fragment}")

    source_collection_names = {
        source.get("collection_name")
        for source in response_sources
        if isinstance(source, dict)
    }

    retrieved_collection_names = {
        chunk.get("collection_name")
        for chunk in retrieved_chunks
        if isinstance(chunk, dict)
    }

    if "logistics_kb_v1" not in source_collection_names | retrieved_collection_names:
        case_errors.append("logistics_kb_v1 not found in sources or retrieved chunks")

    return {
        "case_id": case_id,
        "query": query,
        "selected_module": result_state.get("selected_module"),
        "intent": result_state.get("intent"),
        "metadata": {
            key: metadata.get(key)
            for key in (
                "real_logistics_kb_retriever_used",
                "real_logistics_kb_retriever_error",
                "retrieval_source",
                "retrieval_selected_module",
                "retrieval_collection_name",
                "retrieval_hit_count",
                "render_mode",
                "render_is_grounded",
                "render_used_llm_output",
                "render_source_count",
                "render_warning_count",
                "render_safety_blocked",
            )
        },
        "retrieved_chunk_count": len(retrieved_chunks),
        "response_source_count": len(response_sources),
        "top_retrieved_chunk": safe_chunk_preview(retrieved_chunks[0])
        if retrieved_chunks
        else None,
        "final_response_preview": final_response[:300],
        "errors": case_errors,
    }


def safe_chunk_preview(
    chunk: Any,
) -> dict[str, Any]:
    """Return safe chunk preview."""

    if not isinstance(chunk, dict):
        return {}

    allowed_keys = {
        "chunk_id",
        "summary",
        "score",
        "source",
        "source_type",
        "source_name",
        "doc_id",
        "doc_title",
        "module",
        "collection_name",
        "risk_level",
        "sku_scope",
        "intent_scope",
        "handoff_required",
        "is_verified",
        "allow_answer_reference",
        "allow_commitment_reference",
    }

    return {
        key: value
        for key, value in chunk.items()
        if key in allowed_keys
    }


def ensure_dict(value: object) -> dict[str, Any]:
    """Return dict value."""

    if isinstance(value, dict):
        return {
            str(key): item_value
            for key, item_value in value.items()
        }

    return {}


def ensure_list(value: object) -> list[Any]:
    """Return list value."""

    if isinstance(value, list):
        return value

    return []


def set_required_env() -> None:
    """Set required env vars for this check."""

    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["LOGISTICS_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    os.environ["EMBEDDING_MAX_RETRIES"] = "2"
    os.environ["EMBEDDING_BATCH_SIZE"] = "8"


def load_env_file(
    env_file: Path,
) -> None:
    """Load simple KEY=VALUE env file without overriding existing env."""

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    """Run check."""

    try:
        passed = check_logistics_kb_grounded_e2e()
    except Exception as exc:
        print(
            "real Logistics KB grounded E2E check crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())