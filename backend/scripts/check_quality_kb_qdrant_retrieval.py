# ruff: noqa: E402,I001
"""Check real Quality KB retrieval from Qdrant quality_kb_v1."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import httpx

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.real_embedding import (
    OpenAICompatibleEmbeddingClient,
    RealEmbeddingConfig,
)


ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "quality_kb_v1"
DEFAULT_TOP_K: Final[int] = 5

QUALITY_TEST_QUERIES: Final[tuple[str, ...]] = (
    "SKU001 这款铝合金6061材质质量怎么样？",
    "SKU001 表面处理是不是阳极氧化黑色？",
    "这个球头有没有检测记录可以证明质量？",
    "SKU001 材质和外观处理能不能做一个品质说明？",
)


def check_quality_kb_retrieval() -> bool:
    """Check Quality KB retrieval."""

    print("=" * 80)
    print("checking quality KB Qdrant retrieval")

    load_env_file(ENV_FILE)

    collection_name = get_quality_collection_name()
    qdrant_url = get_qdrant_url()
    top_k = get_top_k()

    result: dict[str, Any] = {
        "collection_name": collection_name,
        "qdrant_url": qdrant_url,
        "top_k": top_k,
        "query_count": len(QUALITY_TEST_QUERIES),
        "results": [],
        "errors": [],
    }

    errors: list[str] = result["errors"]

    try:
        verify_collection_ready(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
        )

        embedding_client = OpenAICompatibleEmbeddingClient(
            config=RealEmbeddingConfig.from_env()
        )

        for query in QUALITY_TEST_QUERIES:
            vector = embedding_client.embed_texts([query])[0]

            hits = search_qdrant(
                qdrant_url=qdrant_url,
                collection_name=collection_name,
                vector=vector,
                top_k=top_k,
            )

            query_result = check_one_query(
                query=query,
                hits=hits,
                expected_collection=collection_name,
            )

            result["results"].append(query_result)

            if query_result["errors"]:
                errors.extend(
                    f"{query}: {error}"
                    for error in query_result["errors"]
                )

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    pprint(result)

    if errors:
        print("quality KB Qdrant retrieval check failed")
        return False

    print("quality KB Qdrant retrieval check passed")
    return True


def verify_collection_ready(
    *,
    qdrant_url: str,
    collection_name: str,
) -> None:
    """Verify collection exists and has points."""

    response = httpx.get(
        f"{qdrant_url}/collections/{collection_name}",
        timeout=30.0,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant collection get failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("Qdrant collection response must be object")

    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError("Qdrant collection result must be object")

    status = result.get("status")
    points_count = result.get("points_count")

    if status != "green":
        raise RuntimeError(f"Qdrant collection status is not green: {status}")

    if not isinstance(points_count, int) or points_count <= 0:
        raise RuntimeError(f"Qdrant collection has no points: {points_count}")


def search_qdrant(
    *,
    qdrant_url: str,
    collection_name: str,
    vector: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    """Search Qdrant with vector."""

    search_payload = {
        "vector": vector,
        "limit": top_k,
        "with_payload": True,
        "with_vector": False,
    }

    response = httpx.post(
        f"{qdrant_url}/collections/{collection_name}/points/search",
        json=search_payload,
        timeout=60.0,
    )

    if response.status_code in {404, 405}:
        query_payload = {
            "query": vector,
            "limit": top_k,
            "with_payload": True,
            "with_vector": False,
        }

        response = httpx.post(
            f"{qdrant_url}/collections/{collection_name}/points/query",
            json=query_payload,
            timeout=60.0,
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant search failed: HTTP {response.status_code}: "
            f"{response.text[:800]}"
        )

    payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("Qdrant search response must be object")

    result = payload.get("result")

    if isinstance(result, dict) and isinstance(result.get("points"), list):
        return normalize_hits(result["points"])

    if isinstance(result, list):
        return normalize_hits(result)

    raise RuntimeError("Qdrant search result shape is unsupported")


def normalize_hits(
    raw_hits: list[Any],
) -> list[dict[str, Any]]:
    """Normalize Qdrant hits."""

    hits: list[dict[str, Any]] = []

    for raw_hit in raw_hits:
        if not isinstance(raw_hit, dict):
            continue

        payload = raw_hit.get("payload")

        if not isinstance(payload, dict):
            payload = {}

        score = raw_hit.get("score")

        if score is None:
            score = raw_hit.get("distance")

        hits.append(
            {
                "id": raw_hit.get("id"),
                "score": score,
                "payload": {
                    str(key): value
                    for key, value in payload.items()
                },
            }
        )

    return hits


def check_one_query(
    *,
    query: str,
    hits: list[dict[str, Any]],
    expected_collection: str,
) -> dict[str, Any]:
    """Check one query result."""

    errors: list[str] = []

    if not hits:
        errors.append("no hits returned")

    top_payload = hits[0]["payload"] if hits else {}

    if top_payload.get("collection_name") != expected_collection:
        errors.append(
            "top hit collection mismatch: "
            f"{top_payload.get('collection_name')}"
        )

    if top_payload.get("module") != "quality":
        errors.append(f"top hit module mismatch: {top_payload.get('module')}")

    if top_payload.get("allow_answer_reference") is not True:
        errors.append("top hit allow_answer_reference must be true")

    if top_payload.get("allow_commitment_reference") is not False:
        errors.append("top hit allow_commitment_reference must be false")

    if not top_payload.get("content"):
        errors.append("top hit content is empty")

    safe_hits = [
        {
            "rank": index + 1,
            "id": hit.get("id"),
            "score": hit.get("score"),
            "chunk_id": hit["payload"].get("chunk_id"),
            "doc_id": hit["payload"].get("doc_id"),
            "module": hit["payload"].get("module"),
            "risk_level": hit["payload"].get("risk_level"),
            "sku_scope": hit["payload"].get("sku_scope"),
            "summary": hit["payload"].get("summary"),
        }
        for index, hit in enumerate(hits)
    ]

    return {
        "query": query,
        "hit_count": len(hits),
        "top_chunk_id": top_payload.get("chunk_id"),
        "top_doc_id": top_payload.get("doc_id"),
        "top_score": hits[0].get("score") if hits else None,
        "top_summary": top_payload.get("summary"),
        "hits": safe_hits,
        "errors": errors,
    }


def get_quality_collection_name() -> str:
    """Return quality collection name."""

    return (
        os.getenv("QDRANT_COLLECTION_QUALITY", "").strip()
        or DEFAULT_COLLECTION_NAME
    )


def get_qdrant_url() -> str:
    """Return Qdrant URL."""

    explicit = os.getenv("QDRANT_URL", "").strip()

    if explicit:
        return explicit.rstrip("/")

    host = os.getenv("QDRANT_HOST", "").strip() or "127.0.0.1"
    port = os.getenv("QDRANT_PORT", "").strip() or "6333"

    return f"http://{host}:{port}".rstrip("/")


def get_top_k() -> int:
    """Return top_k."""

    value = os.getenv("QUALITY_KB_TOP_K", "").strip()

    if value.isdigit():
        return max(1, min(int(value), 10))

    return DEFAULT_TOP_K


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
        passed = check_quality_kb_retrieval()
    except Exception as exc:
        print(
            "quality KB Qdrant retrieval check crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())