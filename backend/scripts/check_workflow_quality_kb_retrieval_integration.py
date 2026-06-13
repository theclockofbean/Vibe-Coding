# ruff: noqa: E402,I001
"""Check workflow integration with real Quality KB retrieval."""

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

TEST_QUERY: Final[str] = "SKU001 这款铝合金6061材质质量怎么样？"


def check_workflow_quality_kb_retrieval_integration() -> bool:
    """Check workflow uses real Quality KB retrieval for quality query."""

    print("=" * 80)
    print("checking workflow real Quality KB retrieval integration")

    load_env_file(ENV_FILE)
    set_required_env()

    session_factory = get_session_factory()

    with session_factory() as session:
        product_repository = ProductRepository(session=session)

        workflow = build_agent_workflow(
            product_repository=product_repository,
            conversation_repository=None,
        )

        initial_state = cast(
            AgentState,
            {
                "current_message": TEST_QUERY,
                "user_message": TEST_QUERY,
                "user_text": TEST_QUERY,
                "query": TEST_QUERY,
                "intent": "quality",
                "selected_module": "quality",
                "candidate_modules": ["quality"],
                "metadata": {
                    "force_llm_intent_classifier": True,
                    "test_case": "workflow_quality_kb_retrieval_integration",
                },
            },
        )

        result_state = workflow.invoke(initial_state)

    metadata = result_state.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    retrieved_chunks = result_state.get("retrieved_chunks")

    if not isinstance(retrieved_chunks, list):
        retrieved_chunks = []

    errors: list[str] = []

    if metadata.get("real_quality_kb_retriever_used") is not True:
        errors.append("real_quality_kb_retriever_used must be true")

    if metadata.get("retrieval_source") != "real_quality_kb":
        errors.append("retrieval_source must be real_quality_kb")

    if metadata.get("retrieval_selected_module") != "quality":
        errors.append("retrieval_selected_module must be quality")

    if metadata.get("retrieval_collection_name") != "quality_kb_v1":
        errors.append("retrieval_collection_name must be quality_kb_v1")

    if not retrieved_chunks:
        errors.append("retrieved_chunks is empty")

    if retrieved_chunks:
        top_chunk = retrieved_chunks[0]

        if not isinstance(top_chunk, dict):
            errors.append("top retrieved chunk must be dict")
        else:
            if top_chunk.get("module") != "quality":
                errors.append("top retrieved chunk module must be quality")

            if top_chunk.get("collection_name") != "quality_kb_v1":
                errors.append(
                    "top retrieved chunk collection_name must be quality_kb_v1"
                )

            if top_chunk.get("allow_answer_reference") is not True:
                errors.append(
                    "top retrieved chunk allow_answer_reference must be true"
                )

            if top_chunk.get("allow_commitment_reference") is not False:
                errors.append(
                    "top retrieved chunk allow_commitment_reference must be false"
                )

            if not top_chunk.get("content"):
                errors.append("top retrieved chunk content is empty")

    safe_result = {
        "selected_module": result_state.get("selected_module"),
        "intent": result_state.get("intent"),
        "metadata": {
            key: metadata.get(key)
            for key in (
                "real_quality_kb_retriever_enabled",
                "real_quality_kb_retriever_used",
                "real_quality_kb_retriever_error",
                "retrieval_source",
                "retrieval_selected_module",
                "retrieval_collection_name",
                "retrieval_hit_count",
            )
        },
        "retrieved_chunk_count": len(retrieved_chunks),
        "top_retrieved_chunk": safe_chunk_preview(retrieved_chunks[0])
        if retrieved_chunks
        else None,
        "errors": errors,
    }

    serialized = json.dumps(safe_result, ensure_ascii=False)
    embedding_api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()

    if embedding_api_key and embedding_api_key in serialized:
        errors.append("EMBEDDING_API_KEY leaked into workflow check result")

    if llm_api_key and llm_api_key in serialized:
        errors.append("LLM_API_KEY leaked into workflow check result")

    pprint(safe_result)

    if errors:
        print("workflow real Quality KB retrieval integration check failed")
        return False

    print("workflow real Quality KB retrieval integration check passed")
    return True


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
        "is_verified",
        "allow_answer_reference",
        "allow_commitment_reference",
    }

    return {
        key: value
        for key, value in chunk.items()
        if key in allowed_keys
    }


def set_required_env() -> None:
    """Set required env vars for this check."""

    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    os.environ["EMBEDDING_MAX_RETRIES"] = "2"
    os.environ["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    os.environ["QUALITY_KB_TOP_K"] = "5"


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
        passed = check_workflow_quality_kb_retrieval_integration()
    except Exception as exc:
        print(
            "workflow real Quality KB retrieval integration check crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())