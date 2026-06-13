"""Check Phase 3-I-F four-KB integration baseline."""

from __future__ import annotations

import json
import os
from pathlib import Path
from pprint import pprint
from typing import Any, Final
from urllib import request


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

EXPECTED_COLLECTIONS: Final[tuple[tuple[str, str, int], ...]] = (
    ("quality", "quality_kb_v1", 50),
    ("logistics", "logistics_kb_v1", 50),
    ("price", "price_kb_v1", 50),
    ("spec", "spec_kb_v1", 23),
)

EXPECTED_RETRIEVER_FILES: Final[tuple[str, ...]] = (
    "app/agent/rag/quality_kb_retriever.py",
    "app/agent/rag/logistics_kb_retriever.py",
    "app/agent/rag/price_kb_retriever.py",
    "app/agent/rag/spec_kb_retriever.py",
)

EXPECTED_TOTAL_REGRESSION_SCRIPTS: Final[tuple[str, ...]] = (
    "scripts/check_phase3ic_logistics_kb_total_regression.py",
    "scripts/check_phase3id_price_kb_total_regression.py",
    "scripts/check_phase3ie_spec_kb_total_regression.py",
)

EXPECTED_WORKFLOW_HELPERS: Final[tuple[str, ...]] = (
    "_try_real_quality_kb_retrieval",
    "_try_real_logistics_kb_retrieval",
    "_try_real_price_kb_retrieval",
    "_try_real_spec_kb_retrieval",
    "_force_logistics_route_for_delivery_question",
    "_force_spec_route_for_spec_kb_question",
)


def main() -> int:
    """Run baseline check."""

    print("=" * 80)
    print("checking Phase 3-I-F four-KB integration baseline")

    set_required_env()

    errors: list[str] = []
    file_results = check_files(errors=errors)
    collection_results = check_collections(errors=errors)
    workflow_result = check_workflow(errors=errors)

    result: dict[str, Any] = {
        "file_results": file_results,
        "collection_results": collection_results,
        "workflow_result": workflow_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-F four-KB baseline check failed")
        return 1

    print("Phase 3-I-F four-KB baseline check passed")
    return 0


def set_required_env() -> None:
    """Set baseline env vars."""

    os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")

    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "1"

    os.environ["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["QDRANT_COLLECTION_PRICE"] = "price_kb_v1"
    os.environ["QDRANT_COLLECTION_SPEC"] = "spec_kb_v1"

    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "240"
    os.environ["EMBEDDING_BATCH_SIZE"] = "1"


def check_files(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check expected files."""

    checked_files = EXPECTED_RETRIEVER_FILES + EXPECTED_TOTAL_REGRESSION_SCRIPTS
    results: list[dict[str, Any]] = []

    for relative_path in checked_files:
        path = BACKEND_ROOT / relative_path
        exists = path.exists()
        results.append({"path": relative_path, "exists": exists})

        if not exists:
            errors.append(f"missing file: {relative_path}")

    return {"checked_count": len(checked_files), "results": results}


def check_collections(
    *,
    errors: list[str],
) -> list[dict[str, Any]]:
    """Check Qdrant collection counts."""

    results: list[dict[str, Any]] = []

    for module, collection_name, expected_count in EXPECTED_COLLECTIONS:
        try:
            actual_count = count_qdrant_points(collection_name=collection_name)
        except Exception as exc:
            errors.append(
                f"{module}: failed to count {collection_name}: "
                f"{type(exc).__name__}: {exc}"
            )
            results.append(
                {
                    "module": module,
                    "collection_name": collection_name,
                    "expected_count": expected_count,
                    "actual_count": None,
                    "passed": False,
                }
            )
            continue

        passed = actual_count == expected_count

        if not passed:
            errors.append(
                f"{module}: expected {expected_count} points in "
                f"{collection_name}, got {actual_count}"
            )

        results.append(
            {
                "module": module,
                "collection_name": collection_name,
                "expected_count": expected_count,
                "actual_count": actual_count,
                "passed": passed,
            }
        )

    return results


def check_workflow(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check workflow helper and hook baseline."""

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        return {"workflow_file": str(WORKFLOW_FILE), "exists": False}

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()

    helper_results: list[dict[str, Any]] = []

    for helper_name in EXPECTED_WORKFLOW_HELPERS:
        line_number = find_line_number(lines=lines, fragment=helper_name)
        found = line_number is not None

        if not found:
            errors.append(f"workflow missing helper or hook: {helper_name}")

        helper_results.append(
            {
                "name": helper_name,
                "found": found,
                "line_number": line_number,
            }
        )

    hook_order = {
        "quality": find_line_number(lines=lines, fragment="real_quality_kb_used"),
        "logistics": find_line_number(lines=lines, fragment="real_logistics_kb_used"),
        "price": find_line_number(lines=lines, fragment="real_price_kb_used"),
        "spec": find_line_number(lines=lines, fragment="real_spec_kb_used"),
    }

    order_values = [
        value
        for value in hook_order.values()
        if value is not None
    ]

    if len(order_values) != 4:
        errors.append(f"workflow hook order incomplete: {hook_order}")
    elif order_values != sorted(order_values):
        errors.append(f"workflow hook order unexpected: {hook_order}")

    return {
        "workflow_file": str(WORKFLOW_FILE),
        "exists": True,
        "helper_results": helper_results,
        "hook_order": hook_order,
    }


def find_line_number(
    *,
    lines: list[str],
    fragment: str,
) -> int | None:
    """Find first line number containing fragment."""

    for index, line in enumerate(lines, start=1):
        if fragment in line:
            return index

    return None


def count_qdrant_points(
    *,
    collection_name: str,
) -> int:
    """Count Qdrant points."""

    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    endpoint = f"{qdrant_url}/collections/{collection_name}/points/count"

    response = post_json(
        endpoint=endpoint,
        payload={"exact": True},
        timeout=60,
    )

    result = response.get("result", {})

    if not isinstance(result, dict):
        raise ValueError("Qdrant count result must be a JSON object")

    return int(result.get("count", 0))


def post_json(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Post JSON and return parsed object."""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310
        raw_response = response.read().decode("utf-8")

    parsed = json.loads(raw_response)

    if not isinstance(parsed, dict):
        raise ValueError("response must be a JSON object")

    return parsed


if __name__ == "__main__":
    raise SystemExit(main())