"""Check Spec KB Qdrant retrieval."""

from __future__ import annotations

import json
import os
from pprint import pprint
from typing import Any, Final, cast
from urllib import request


COLLECTION_NAME: Final[str] = "spec_kb_v1"
EXPECTED_COUNT: Final[int] = 23
EXPECTED_DIMENSION: Final[int] = 1024
TOP_K: Final[int] = 5

TEST_QUERIES: Final[list[str]] = [
    "SKU001是什么规格？",
    "SKU001的螺纹规格是多少？",
    "M10的球头有哪些？",
    "杆长120mm有吗？",
    "这个球头能通用适配吗？",
]


def main() -> int:
    """Run Spec KB Qdrant retrieval check."""

    print("=" * 80)
    print("checking Spec KB Qdrant retrieval")

    set_required_env()

    errors: list[str] = []

    qdrant_count = count_qdrant_points()

    if qdrant_count != EXPECTED_COUNT:
        errors.append(
            f"expected {EXPECTED_COUNT} Qdrant points, got {qdrant_count}"
        )

    retrieval_results: list[dict[str, Any]] = []

    for query in TEST_QUERIES:
        vector = embed_one(text=query)

        if len(vector) != EXPECTED_DIMENSION:
            errors.append(
                f"{query}: vector dimension must be "
                f"{EXPECTED_DIMENSION}, got {len(vector)}"
            )
            continue

        hits = search_qdrant(vector=vector, limit=TOP_K)

        if not hits:
            errors.append(f"{query}: no Qdrant hits")
            continue

        validate_hits(query=query, hits=hits, errors=errors)
        retrieval_results.append(preview_result(query=query, hits=hits))

    result: dict[str, Any] = {
        "collection_name": COLLECTION_NAME,
        "qdrant_count": qdrant_count,
        "expected_count": EXPECTED_COUNT,
        "embedding_dimension": EXPECTED_DIMENSION,
        "top_k": TOP_K,
        "query_count": len(TEST_QUERIES),
        "retrieval_results": retrieval_results,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Spec KB Qdrant retrieval check failed")
        return 1

    print("Spec KB Qdrant retrieval check passed")
    return 0


def set_required_env() -> None:
    """Set required embedding env vars."""

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = str(EXPECTED_DIMENSION)
    os.environ.setdefault("EMBEDDING_TIMEOUT_SECONDS", "240")


def count_qdrant_points() -> int:
    """Count Qdrant points."""

    qdrant_url = read_qdrant_url()
    endpoint = f"{qdrant_url}/collections/{COLLECTION_NAME}/points/count"
    response = post_json(
        endpoint=endpoint,
        payload={"exact": True},
        timeout=60,
    )

    result = cast(dict[str, Any], response.get("result", {}))
    return int(result.get("count", 0))


def embed_one(
    *,
    text: str,
) -> list[float]:
    """Embed one query."""

    base_url = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "240"))
    endpoint = f"{base_url}/embed"

    response = post_json(
        endpoint=endpoint,
        payload={"inputs": [text]},
        timeout=timeout,
    )

    if not isinstance(response, list) or not response:
        raise ValueError("embedding response must be a non-empty list")

    vector = response[0]

    if not isinstance(vector, list):
        raise ValueError("embedding vector must be a list")

    return [float(value) for value in vector]


def search_qdrant(
    *,
    vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Search Qdrant."""

    qdrant_url = read_qdrant_url()
    endpoint = f"{qdrant_url}/collections/{COLLECTION_NAME}/points/search"

    response = post_json(
        endpoint=endpoint,
        payload={
            "vector": vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        },
        timeout=120,
    )

    hits = response.get("result", [])

    if not isinstance(hits, list):
        raise ValueError("Qdrant search result must be a list")

    return [
        cast(dict[str, Any], hit)
        for hit in hits
        if isinstance(hit, dict)
    ]


def validate_hits(
    *,
    query: str,
    hits: list[dict[str, Any]],
    errors: list[str],
) -> None:
    """Validate Qdrant hits."""

    top_hit = hits[0]
    payload = cast(dict[str, Any], top_hit.get("payload", {}))

    chunk_id = str(payload.get("chunk_id", ""))

    if not chunk_id.startswith("spec_qa_spec"):
        errors.append(f"{query}: top hit chunk_id is not Spec KB chunk: {chunk_id}")

    if payload.get("collection_name") != COLLECTION_NAME:
        errors.append(
            f"{query}: payload collection_name mismatch: "
            f"{payload.get('collection_name')}"
        )

    if payload.get("module") != "spec":
        errors.append(f"{query}: payload module must be spec")

    if payload.get("allow_answer_reference") is not True:
        errors.append(f"{query}: allow_answer_reference must be true")

    if payload.get("allow_commitment_reference") is not False:
        errors.append(f"{query}: allow_commitment_reference must be false")

    if not str(payload.get("content", "")).strip():
        errors.append(f"{query}: payload content is empty")

    if not str(payload.get("answer_standard", "")).strip():
        errors.append(f"{query}: payload answer_standard is empty")


def preview_result(
    *,
    query: str,
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preview retrieval result."""

    preview_hits: list[dict[str, Any]] = []

    for hit in hits[:3]:
        payload = cast(dict[str, Any], hit.get("payload", {}))
        preview_hits.append(
            {
                "score": hit.get("score"),
                "chunk_id": payload.get("chunk_id"),
                "qa_id": payload.get("qa_id"),
                "module": payload.get("module"),
                "intent_subtype": payload.get("intent_subtype"),
                "question_normalized": payload.get("question_normalized"),
                "answer_standard_preview": str(
                    payload.get("answer_standard", "")
                )[:180],
            }
        )

    return {
        "query": query,
        "hit_count": len(hits),
        "top_hits": preview_hits,
    }


def post_json(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout: float,
) -> Any:
    """Post JSON and return parsed response."""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310
        raw_response = response.read().decode("utf-8")

    if not raw_response.strip():
        return {}

    return json.loads(raw_response)


def read_qdrant_url() -> str:
    """Read Qdrant URL."""

    return os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")


if __name__ == "__main__":
    raise SystemExit(main())