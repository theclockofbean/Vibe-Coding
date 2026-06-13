# ruff: noqa: E402,I001
"""Check real Spec KB retrieval plus grounded final response."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import AgentState
from app.agent.workflow import build_agent_workflow
from app.core.database import get_session_factory
from app.repositories import ProductRepository


EXPECTED_COLLECTION_NAME: Final[str] = "spec_kb_v1"

TEST_CASES: Final[tuple[dict[str, str], ...]] = (
    {
        "case_id": "SPEC_E2E_001",
        "query": "SKU001是什么规格？",
    },
    {
        "case_id": "SPEC_E2E_002",
        "query": "SKU001的螺纹规格是多少？",
    },
    {
        "case_id": "SPEC_E2E_003",
        "query": "M10的球头有哪些？",
    },
    {
        "case_id": "SPEC_E2E_004",
        "query": "杆长120mm有吗？",
    },
    {
        "case_id": "SPEC_E2E_005",
        "query": "这个球头能通用适配吗？",
    },
)


FORBIDDEN_RESPONSE_FRAGMENTS: Final[tuple[str, ...]] = (
    "万能适配",
    "百分百适配",
    "一定适配",
    "保证适配",
    "全部车型都能用",
    "不用核对直接能用",
)



def main() -> int:
    """Run Spec KB grounded E2E check."""

    print("=" * 80)
    print("checking real Spec KB grounded E2E")

    set_required_env()

    errors: list[str] = []
    case_results: list[dict[str, Any]] = []

    session_factory = get_session_factory()

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

    safe_result: dict[str, Any] = {
        "case_count": len(TEST_CASES),
        "results": case_results,
        "errors": errors,
    }

    pprint(safe_result)

    if errors:
        print("real Spec KB grounded E2E check failed")
        return 1

    print("real Spec KB grounded E2E check passed")
    return 0


def run_one_case(
    *,
    workflow: Any,
    case_id: str,
    query: str,
) -> dict[str, Any]:
    """Run one E2E case."""

    initial_state = cast(
        AgentState,
        {
            "current_message": query,
            "user_message": query,
            "user_text": query,
            "query": query,
            "intent": "spec",
            "selected_module": "spec",
            "candidate_modules": ["spec"],
            "metadata": {
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

    errors: list[str] = []

    if metadata.get("real_spec_kb_retriever_used") is not True:
        errors.append("real_spec_kb_retriever_used must be true")

    if metadata.get("retrieval_source") != "real_spec_kb":
        errors.append("retrieval_source must be real_spec_kb")

    if metadata.get("retrieval_selected_module") != "spec":
        errors.append("retrieval_selected_module must be spec")

    if metadata.get("retrieval_collection_name") != EXPECTED_COLLECTION_NAME:
        errors.append("retrieval_collection_name must be spec_kb_v1")

    if not retrieved_chunks:
        errors.append("retrieved_chunks is empty")

    if retrieved_chunks:
        top_chunk = ensure_dict(retrieved_chunks[0])

        if top_chunk.get("collection_name") != EXPECTED_COLLECTION_NAME:
            errors.append("top retrieved chunk collection_name must be spec_kb_v1")

        if top_chunk.get("module") != "spec":
            errors.append("top retrieved chunk module must be spec")

        if top_chunk.get("allow_answer_reference") is not True:
            errors.append("top chunk allow_answer_reference must be true")

        if top_chunk.get("allow_commitment_reference") is not False:
            errors.append("top chunk allow_commitment_reference must be false")

        if not str(top_chunk.get("content", "")).strip():
            errors.append("top retrieved chunk content is empty")

    if not final_response:
        errors.append("final_response is empty")

    for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
        if fragment in final_response:
            errors.append(f"final_response contains forbidden fragment: {fragment}")

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

    if EXPECTED_COLLECTION_NAME not in source_collection_names | retrieved_collection_names:
        errors.append("spec_kb_v1 not found in sources or retrieved chunks")

    return {
        "case_id": case_id,
        "query": query,
        "intent": result_state.get("intent"),
        "selected_module": result_state.get("selected_module"),
        "metadata": {
            key: metadata.get(key)
            for key in (
                "real_spec_kb_retriever_used",
                "real_spec_kb_retriever_error",
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
        "errors": errors,
    }


def set_required_env() -> None:
    """Set required env vars."""

    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_SPEC"] = EXPECTED_COLLECTION_NAME
    os.environ["SPEC_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"


def ensure_dict(
    value: object,
) -> dict[str, Any]:
    """Return dict value."""

    if isinstance(value, dict):
        return {
            str(key): item_value
            for key, item_value in value.items()
        }

    return {}


def ensure_list(
    value: object,
) -> list[Any]:
    """Return list value."""

    if isinstance(value, list):
        return value

    return []


def safe_chunk_preview(
    chunk: Any,
) -> dict[str, Any]:
    """Return safe chunk preview."""

    if not isinstance(chunk, dict):
        return {}

    allowed_keys = {
        "chunk_id",
        "doc_id",
        "doc_title",
        "summary",
        "score",
        "collection_name",
        "module",
        "source_type",
        "source_name",
        "qa_id",
        "intent_subtype",
        "risk_flags",
        "risk_level",
        "allow_answer_reference",
        "allow_commitment_reference",
        "is_verified",
    }

    return {
        key: value
        for key, value in chunk.items()
        if key in allowed_keys
    }


if __name__ == "__main__":
    raise SystemExit(main())