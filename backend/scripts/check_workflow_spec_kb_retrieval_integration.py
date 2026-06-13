# ruff: noqa: E402,I001
"""Check workflow integration with real Spec KB retriever."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.workflow import _try_real_spec_kb_retrieval


TEST_CASES: Final[list[dict[str, Any]]] = [
    {
        "case_id": "SPEC_WORKFLOW_001",
        "query": "SKU001是什么规格？",
        "selected_module": "spec",
    },
    {
        "case_id": "SPEC_WORKFLOW_002",
        "query": "SKU001的螺纹规格是多少？",
        "selected_module": "spec",
    },
    {
        "case_id": "SPEC_WORKFLOW_003",
        "query": "M10的球头有哪些？",
        "selected_module": "spec",
    },
    {
        "case_id": "SPEC_WORKFLOW_004",
        "query": "杆长120mm有吗？",
        "selected_module": "spec",
    },
    {
        "case_id": "SPEC_WORKFLOW_005",
        "query": "这个球头能通用适配吗？",
        "selected_module": "spec",
    },
]


def main() -> int:
    """Run workflow Spec KB integration check."""

    print("=" * 80)
    print("checking workflow Spec KB retriever integration")

    set_required_env()

    errors: list[str] = []
    case_results: list[dict[str, Any]] = []

    for test_case in TEST_CASES:
        state = build_state(test_case=test_case)
        new_state, used = _try_real_spec_kb_retrieval(state)

        validate_result(
            test_case=test_case,
            new_state=cast(dict[str, Any], new_state),
            used=used,
            errors=errors,
        )

        case_results.append(
            preview_case_result(
                test_case=test_case,
                new_state=cast(dict[str, Any], new_state),
                used=used,
            )
        )

    result: dict[str, Any] = {
        "case_count": len(TEST_CASES),
        "collection_name": os.getenv("QDRANT_COLLECTION_SPEC"),
        "spec_kb_retriever_enabled": os.getenv("SPEC_KB_RETRIEVER_ENABLED"),
        "spec_kb_top_k": os.getenv("SPEC_KB_TOP_K"),
        "case_results": case_results,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Workflow Spec KB retrieval integration check failed")
        return 1

    print("Workflow Spec KB retrieval integration check passed")
    return 0


def set_required_env() -> None:
    """Set required env vars."""

    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_SPEC"] = "spec_kb_v1"
    os.environ["SPEC_KB_COLLECTION_NAME"] = "spec_kb_v1"
    os.environ["SPEC_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "240"


def build_state(
    *,
    test_case: dict[str, Any],
) -> dict[str, Any]:
    """Build workflow state."""

    query = str(test_case["query"])
    selected_module = str(test_case["selected_module"])

    return {
        "user_text": query,
        "current_message": query,
        "query": query,
        "selected_module": selected_module,
        "intent": selected_module,
        "candidate_modules": [selected_module],
        "metadata": {},
        "retrieved_chunks": [],
    }


def validate_result(
    *,
    test_case: dict[str, Any],
    new_state: dict[str, Any],
    used: bool,
    errors: list[str],
) -> None:
    """Validate one workflow integration result."""

    case_id = str(test_case["case_id"])
    metadata = cast(dict[str, Any], new_state.get("metadata") or {})

    if used is not True:
        errors.append(f"{case_id}: real Spec KB retriever was not used")

    if metadata.get("real_spec_kb_retriever_enabled") is not True:
        errors.append(f"{case_id}: real_spec_kb_retriever_enabled must be true")

    if metadata.get("real_spec_kb_retriever_used") is not True:
        errors.append(f"{case_id}: real_spec_kb_retriever_used must be true")

    if metadata.get("real_spec_kb_retriever_error") is not None:
        errors.append(
            f"{case_id}: unexpected retriever error: "
            f"{metadata.get('real_spec_kb_retriever_error')}"
        )

    if metadata.get("real_spec_kb_retriever_collection_name") != "spec_kb_v1":
        errors.append(f"{case_id}: collection metadata mismatch")

    if metadata.get("retrieval_source") != "real_spec_kb":
        errors.append(f"{case_id}: retrieval_source metadata mismatch")

    if metadata.get("retrieval_collection_name") != "spec_kb_v1":
        errors.append(f"{case_id}: retrieval_collection_name metadata mismatch")

    retrieved_chunks = new_state.get("retrieved_chunks")

    if not isinstance(retrieved_chunks, list) or not retrieved_chunks:
        errors.append(f"{case_id}: retrieved_chunks must be non-empty")
        return

    top_chunk = retrieved_chunks[0]

    if not isinstance(top_chunk, dict):
        errors.append(f"{case_id}: top retrieved chunk must be dict")
        return

    validate_top_chunk(case_id=case_id, top_chunk=top_chunk, errors=errors)


def validate_top_chunk(
    *,
    case_id: str,
    top_chunk: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate top retrieved chunk."""

    payload = cast(dict[str, Any], top_chunk.get("payload") or {})
    chunk_id = str(top_chunk.get("chunk_id") or payload.get("chunk_id") or "")

    if not chunk_id.startswith("spec_qa_spec"):
        errors.append(f"{case_id}: top chunk_id must be Spec KB chunk")

    if top_chunk.get("collection_name") != "spec_kb_v1":
        errors.append(f"{case_id}: top chunk collection_name mismatch")

    if top_chunk.get("module") != "spec":
        errors.append(f"{case_id}: top chunk module must be spec")

    if top_chunk.get("allow_answer_reference") is not True:
        errors.append(f"{case_id}: allow_answer_reference must be true")

    if top_chunk.get("allow_commitment_reference") is not False:
        errors.append(f"{case_id}: allow_commitment_reference must be false")

    if not str(top_chunk.get("answer_standard", "")).strip():
        errors.append(f"{case_id}: answer_standard is empty")

    if not str(top_chunk.get("content", "")).strip():
        errors.append(f"{case_id}: content is empty")


def preview_case_result(
    *,
    test_case: dict[str, Any],
    new_state: dict[str, Any],
    used: bool,
) -> dict[str, Any]:
    """Preview one case result."""

    metadata = cast(dict[str, Any], new_state.get("metadata") or {})
    retrieved_chunks = new_state.get("retrieved_chunks") or []

    top_chunks: list[dict[str, Any]] = []

    if isinstance(retrieved_chunks, list):
        for chunk in retrieved_chunks[:3]:
            if isinstance(chunk, dict):
                top_chunks.append(
                    {
                        "score": chunk.get("score"),
                        "chunk_id": chunk.get("chunk_id"),
                        "qa_id": chunk.get("qa_id"),
                        "module": chunk.get("module"),
                        "intent_subtype": chunk.get("intent_subtype"),
                        "question_normalized": chunk.get("question_normalized"),
                        "answer_standard_preview": str(
                            chunk.get("answer_standard", "")
                        )[:160],
                    }
                )

    return {
        "case_id": test_case["case_id"],
        "query": test_case["query"],
        "used": used,
        "metadata_used": metadata.get("real_spec_kb_retriever_used"),
        "hit_count": metadata.get("real_spec_kb_retriever_hit_count"),
        "retrieval_source": metadata.get("retrieval_source"),
        "retrieval_collection_name": metadata.get("retrieval_collection_name"),
        "top_chunks": top_chunks,
    }


if __name__ == "__main__":
    raise SystemExit(main())