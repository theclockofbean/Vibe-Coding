# ruff: noqa: E402,I001
"""Check Phase 3-I-F conflict cases through workflow routing and real KB retrieval."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from collections.abc import Callable
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.workflow import _apply_unified_kb_routing
from app.agent.workflow import _try_real_logistics_kb_retrieval
from app.agent.workflow import _try_real_price_kb_retrieval
from app.agent.workflow import _try_real_spec_kb_retrieval


JSON_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3if_cross_module_conflict_cases_v0.1.json"
)

EXPECTED_CASE_COUNT: Final[int] = 15

RetrievalHelper = Callable[[dict[str, Any]], tuple[dict[str, Any], bool]]

RETRIEVAL_HELPERS: Final[dict[str, RetrievalHelper]] = {
    "price": cast(RetrievalHelper, _try_real_price_kb_retrieval),
    "logistics": cast(RetrievalHelper, _try_real_logistics_kb_retrieval),
    "spec": cast(RetrievalHelper, _try_real_spec_kb_retrieval),
}


def main() -> int:
    """Run conflict Workflow E2E check."""

    print("=" * 80)
    print("checking Phase 3-I-F conflict Workflow E2E")

    set_required_env()

    errors: list[str] = []

    if not JSON_FILE.exists():
        errors.append(f"missing JSON file: {JSON_FILE}")
        pprint({"errors": errors})
        return 1

    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        errors.append("JSON root must be object")
        pprint({"errors": errors})
        return 1

    cases = cast(list[dict[str, Any]], data.get("cases", []))
    module_collections = cast(dict[str, str], data.get("module_collections", {}))
    module_sources = cast(dict[str, str], data.get("module_sources", {}))

    if len(cases) != EXPECTED_CASE_COUNT:
        errors.append(f"expected {EXPECTED_CASE_COUNT} cases, got {len(cases)}")

    results: list[dict[str, Any]] = []

    for case in cases:
        result = validate_case(
            case=case,
            module_collections=module_collections,
            module_sources=module_sources,
            errors=errors,
        )
        results.append(result)

    summary = {
        "case_count": len(cases),
        "error_count": len(errors),
        "passed_count": len(cases) - len({error.split(':', 1)[0] for error in errors}),
        "results": results,
        "errors": errors,
    }

    pprint(summary)

    if errors:
        print("Phase 3-I-F conflict Workflow E2E check failed")
        return 1

    print("Phase 3-I-F conflict Workflow E2E check passed")
    return 0


def set_required_env() -> None:
    """Set required env vars for real KB retrieval."""

    os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")

    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "1"

    os.environ["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["QDRANT_COLLECTION_PRICE"] = "price_kb_v1"
    os.environ["QDRANT_COLLECTION_SPEC"] = "spec_kb_v1"

    os.environ["QUALITY_KB_COLLECTION_NAME"] = "quality_kb_v1"
    os.environ["LOGISTICS_KB_COLLECTION_NAME"] = "logistics_kb_v1"
    os.environ["PRICE_KB_COLLECTION_NAME"] = "price_kb_v1"
    os.environ["SPEC_KB_COLLECTION_NAME"] = "spec_kb_v1"

    os.environ["QUALITY_KB_TOP_K"] = "5"
    os.environ["LOGISTICS_KB_TOP_K"] = "5"
    os.environ["PRICE_KB_TOP_K"] = "5"
    os.environ["SPEC_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "240"
    os.environ["EMBEDDING_BATCH_SIZE"] = "1"


def validate_case(
    *,
    case: dict[str, Any],
    module_collections: dict[str, str],
    module_sources: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one conflict case through workflow routing and retrieval."""

    case_id = str(case["case_id"])
    query = str(case["query"])
    expected_module = str(case["expected_module"])
    expected_conflict_type = str(case["conflict_type"])
    expected_collection = module_collections[expected_module]
    expected_source = module_sources[expected_module]

    state: dict[str, Any] = {
        "user_text": query,
        "current_message": query,
        "user_message": query,
        "query": query,
        "metadata": {},
        "retrieved_chunks": [],
    }

    routed_state = cast(dict[str, Any], _apply_unified_kb_routing(cast(Any, state)))
    routing_metadata = cast(dict[str, Any], routed_state.get("metadata") or {})

    helper = RETRIEVAL_HELPERS.get(expected_module)
    case_errors: list[str] = []

    if helper is None:
        case_errors.append(f"missing retrieval helper for module: {expected_module}")
        for error in case_errors:
            errors.append(f"{case_id}: {error}")
        return build_result(
            case_id=case_id,
            query=query,
            expected_module=expected_module,
            expected_conflict_type=expected_conflict_type,
            routed_state=routed_state,
            final_state=routed_state,
            retrieval_used=False,
            case_errors=case_errors,
        )

    if routed_state.get("selected_module") != expected_module:
        case_errors.append(
            f"selected_module expected {expected_module}, "
            f"got {routed_state.get('selected_module')}"
        )

    if routing_metadata.get("unified_kb_conflict_type") != expected_conflict_type:
        case_errors.append(
            f"conflict_type expected {expected_conflict_type}, "
            f"got {routing_metadata.get('unified_kb_conflict_type')}"
        )

    final_state, retrieval_used = helper(routed_state)
    final_metadata = cast(dict[str, Any], final_state.get("metadata") or {})
    retrieved_chunks = cast(list[dict[str, Any]], final_state.get("retrieved_chunks") or [])

    if retrieval_used is not True:
        case_errors.append("real KB retrieval was not used")

    if not retrieved_chunks:
        case_errors.append("retrieved_chunks is empty")

    if final_metadata.get("retrieval_selected_module") != expected_module:
        case_errors.append(
            "metadata retrieval_selected_module expected "
            f"{expected_module}, got {final_metadata.get('retrieval_selected_module')}"
        )

    if final_metadata.get("retrieval_source") != expected_source:
        case_errors.append(
            f"metadata retrieval_source expected {expected_source}, "
            f"got {final_metadata.get('retrieval_source')}"
        )

    if final_metadata.get("retrieval_collection_name") != expected_collection:
        case_errors.append(
            "metadata retrieval_collection_name expected "
            f"{expected_collection}, got {final_metadata.get('retrieval_collection_name')}"
        )

    hit_count = final_metadata.get("retrieval_hit_count")

    if not isinstance(hit_count, int) or hit_count <= 0:
        module_hit_count = final_metadata.get(f"real_{expected_module}_kb_retriever_hit_count")

        if not isinstance(module_hit_count, int) or module_hit_count <= 0:
            case_errors.append("metadata retrieval_hit_count is missing or invalid")

    for index, chunk in enumerate(retrieved_chunks[:3], start=1):
        chunk_module = chunk.get("module")
        collection_name = (
            chunk.get("collection_name")
            or chunk.get("qdrant_collection_name")
            or chunk.get("retrieval_collection_name")
        )

        if chunk_module is not None and chunk_module != expected_module:
            case_errors.append(
                f"chunk[{index}] module expected {expected_module}, got {chunk_module}"
            )

        if collection_name is not None and collection_name != expected_collection:
            case_errors.append(
                f"chunk[{index}] collection expected {expected_collection}, "
                f"got {collection_name}"
            )

    for error in case_errors:
        errors.append(f"{case_id}: {error}")

    return build_result(
        case_id=case_id,
        query=query,
        expected_module=expected_module,
        expected_conflict_type=expected_conflict_type,
        routed_state=routed_state,
        final_state=final_state,
        retrieval_used=retrieval_used,
        case_errors=case_errors,
    )


def build_result(
    *,
    case_id: str,
    query: str,
    expected_module: str,
    expected_conflict_type: str,
    routed_state: dict[str, Any],
    final_state: dict[str, Any],
    retrieval_used: bool,
    case_errors: list[str],
) -> dict[str, Any]:
    """Build case result."""

    routing_metadata = cast(dict[str, Any], routed_state.get("metadata") or {})
    final_metadata = cast(dict[str, Any], final_state.get("metadata") or {})
    retrieved_chunks = cast(list[dict[str, Any]], final_state.get("retrieved_chunks") or [])

    return {
        "case_id": case_id,
        "query": query,
        "expected_module": expected_module,
        "selected_module": routed_state.get("selected_module"),
        "expected_conflict_type": expected_conflict_type,
        "unified_kb_conflict_type": routing_metadata.get("unified_kb_conflict_type"),
        "retrieval_used": retrieval_used,
        "retrieval_source": final_metadata.get("retrieval_source"),
        "retrieval_collection_name": final_metadata.get("retrieval_collection_name"),
        "retrieval_selected_module": final_metadata.get("retrieval_selected_module"),
        "retrieval_hit_count": final_metadata.get("retrieval_hit_count"),
        "retrieved_chunk_count": len(retrieved_chunks),
        "top_chunk_id": retrieved_chunks[0].get("chunk_id") if retrieved_chunks else None,
        "errors": case_errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())