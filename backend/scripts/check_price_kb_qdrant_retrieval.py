"""Check Price KB Qdrant retrieval with real local embedding."""

from __future__ import annotations

import json
import os
from pprint import pprint
from typing import Any, Final
from urllib import request


COLLECTION_NAME: Final[str] = "price_kb_v1"
EXPECTED_COUNT: Final[int] = 50
EXPECTED_DIMENSION: Final[int] = 1024
TOP_K: Final[int] = 5

TEST_QUERIES: Final[tuple[str, ...]] = (
    "SKU001多少钱？",
    "这个能不能便宜点？",
    "批量采购有没有折扣？",
    "能不能给最低价？",
    "含税价格怎么算？",
)


def main() -> int:
    """Run Price KB Qdrant retrieval check."""

    print("=" * 80)
    print("checking Price KB Qdrant retrieval")

    set_required_env()

    errors: list[str] = []

    collection_info = get_collection_info()
    points_count = int(collection_info.get("points_count") or 0)

    if points_count != EXPECTED_COUNT:
        errors.append(f"expected {EXPECTED_COUNT} points, got {points_count}")

    query_results: list[dict[str, Any]] = []

    for query in TEST_QUERIES:
        vector = embed_text(query)

        if len(vector) != EXPECTED_DIMENSION:
            errors.append(
                f"query vector dimension must be {EXPECTED_DIMENSION}, "
                f"got {len(vector)}"
            )
            continue

        hits = search_qdrant(vector=vector, limit=TOP_K)
        query_result = validate_hits(query=query, hits=hits)
        query_results.append(query_result)
        errors.extend(
            f"{query}: {error}"
            for error in query_result["errors"]
        )

    result: dict[str, Any] = {
        "collection_name": COLLECTION_NAME,
        "points_count": points_count,
        "test_query_count": len(TEST_QUERIES),
        "query_results": query_results,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Price KB Qdrant retrieval check failed")
        return 1

    print("Price KB Qdrant retrieval check passed")
    return 0


def set_required_env() -> None:
    """Set required env vars."""

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = str(EXPECTED_DIMENSION)
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    os.environ["EMBEDDING_MAX_RETRIES"] = "2"


def get_collection_info() -> dict[str, Any]:
    """Get Qdrant collection info."""

    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    url = f"{qdrant_url}/collections/{COLLECTION_NAME}"

    parsed = request_json(
        url=url,
        payload=None,
        method="GET",
        timeout=30,
    )

    result = parsed.get("result")

    if not isinstance(result, dict):
        raise ValueError("Qdrant collection info result must be object")

    return {
        str(key): value
        for key, value in result.items()
    }


def embed_text(
    text: str,
) -> list[float]:
    """Embed one text through local TEI."""

    vectors = embed_texts([text])

    if len(vectors) != 1:
        raise ValueError(f"expected 1 embedding, got {len(vectors)}")

    return vectors[0]


def embed_texts(
    texts: list[str],
) -> list[list[float]]:
    """Embed texts through local TEI HTTP API."""

    base_url = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "120"))
    endpoint = f"{base_url}/embed"

    parsed = request_json(
        url=endpoint,
        payload={"inputs": texts},
        method="POST",
        timeout=timeout,
    )

    if not isinstance(parsed, list):
        raise ValueError("embedding response must be a list")

    vectors: list[list[float]] = []

    for index, item in enumerate(parsed):
        if not isinstance(item, list):
            raise ValueError(f"embedding item {index} must be a list")

        vectors.append([float(value) for value in item])

    return vectors


def search_qdrant(
    *,
    vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Search Qdrant collection."""

    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    endpoint = f"{qdrant_url}/collections/{COLLECTION_NAME}/points/search"

    parsed = request_json(
        url=endpoint,
        payload={
            "vector": vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        },
        method="POST",
        timeout=120,
    )

    result = parsed.get("result")

    if not isinstance(result, list):
        raise ValueError("Qdrant search result must be list")

    hits: list[dict[str, Any]] = []

    for item in result:
        if isinstance(item, dict):
            hits.append(item)

    return hits


def validate_hits(
    *,
    query: str,
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate Qdrant hits."""

    errors: list[str] = []

    if not hits:
        errors.append("empty hits")

    top_payload = get_payload(hits[0]) if hits else {}
    top_score = hits[0].get("score") if hits else None

    if top_payload:
        if top_payload.get("collection_name") != COLLECTION_NAME:
            errors.append("top payload collection_name must be price_kb_v1")

        if top_payload.get("module") != "price":
            errors.append("top payload module must be price")

        if top_payload.get("allow_answer_reference") is not True:
            errors.append("top payload allow_answer_reference must be true")

        if top_payload.get("allow_commitment_reference") is not False:
            errors.append("top payload allow_commitment_reference must be false")

        if not str(top_payload.get("content", "")).strip():
            errors.append("top payload content is empty")

        if not str(top_payload.get("chunk_id", "")).startswith("price_qa_price"):
            errors.append("top payload chunk_id must start with price_qa_price")

    return {
        "query": query,
        "hit_count": len(hits),
        "top_score": top_score,
        "top_payload": safe_payload_preview(top_payload),
        "errors": errors,
    }


def get_payload(
    hit: dict[str, Any],
) -> dict[str, Any]:
    """Get hit payload."""

    payload = hit.get("payload")

    if not isinstance(payload, dict):
        return {}

    return {
        str(key): value
        for key, value in payload.items()
    }


def safe_payload_preview(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Return safe payload preview."""

    allowed_keys = {
        "chunk_id",
        "doc_id",
        "doc_title",
        "summary",
        "collection_name",
        "module",
        "source_type",
        "source_name",
        "qa_id",
        "intent_subtype",
        "related_sku_ids",
        "required_fields",
        "handoff_required",
        "risk_flags",
        "risk_level",
        "allow_answer_reference",
        "allow_commitment_reference",
        "is_verified",
    }

    return {
        key: value
        for key, value in payload.items()
        if key in allowed_keys
    }


def request_json(
    *,
    url: str,
    payload: dict[str, Any] | None,
    method: str,
    timeout: float,
) -> Any:
    """Request JSON."""

    data = None if payload is None else json.dumps(payload).encode("utf-8")

    http_request = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )

    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310
        raw_response = response.read().decode("utf-8")

    return json.loads(raw_response)


if __name__ == "__main__":
    raise SystemExit(main())