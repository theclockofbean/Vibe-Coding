"""Check Logistics KB retrieval from Qdrant logistics_kb_v1."""

from __future__ import annotations

import json
import os
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import httpx


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "logistics"
    / "logistics_kb_qdrant_retrieval_check_result.json"
)

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "logistics_kb_v1"
DEFAULT_EMBEDDING_BASE_URL: Final[str] = "http://127.0.0.1:8088"
DEFAULT_EMBEDDING_MODEL: Final[str] = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIMENSION: Final[int] = 1024
DEFAULT_TOP_K: Final[int] = 5

TEST_QUERIES: Final[tuple[str, ...]] = (
    "SKU001今天拍什么时候发货？",
    "发浙江大概几天能到？",
    "这个订单包邮吗？",
    "偏远地区运费怎么确认？",
    "物流损坏了怎么处理？",
)


def check_logistics_kb_qdrant_retrieval() -> bool:
    """Check logistics_kb_v1 retrieval."""

    print("=" * 80)
    print("checking Logistics KB Qdrant retrieval")

    load_env_file(ENV_FILE)

    qdrant_url = get_qdrant_url()
    collection_name = os.getenv(
        "QDRANT_COLLECTION_LOGISTICS",
        DEFAULT_COLLECTION_NAME,
    ).strip() or DEFAULT_COLLECTION_NAME
    embedding_base_url = os.getenv(
        "EMBEDDING_BASE_URL",
        DEFAULT_EMBEDDING_BASE_URL,
    ).strip() or DEFAULT_EMBEDDING_BASE_URL
    embedding_model = os.getenv(
        "EMBEDDING_MODEL",
        DEFAULT_EMBEDDING_MODEL,
    ).strip() or DEFAULT_EMBEDDING_MODEL
    expected_dimension = get_int_env(
        "EMBEDDING_DIMENSION",
        DEFAULT_EMBEDDING_DIMENSION,
    )
    top_k = get_int_env("LOGISTICS_KB_TOP_K", DEFAULT_TOP_K)

    errors: list[str] = []
    query_results: list[dict[str, Any]] = []

    with httpx.Client(timeout=120.0) as client:
        collection_info = get_collection(
            client=client,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
        )

        points_count = collection_info.get("points_count")
        vectors = extract_vectors_config(collection_info)

        if vectors.get("size") != expected_dimension:
            errors.append(
                f"collection vector size must be {expected_dimension}, "
                f"got {vectors.get('size')}"
            )

        if str(vectors.get("distance")).lower() != "cosine":
            errors.append(f"collection distance must be Cosine, got {vectors.get('distance')}")

        if points_count != 50:
            errors.append(f"collection points_count must be 50, got {points_count}")

        query_vectors = embed_texts(
            client=client,
            embedding_base_url=embedding_base_url,
            embedding_model=embedding_model,
            texts=list(TEST_QUERIES),
        )

        for query, vector in zip(TEST_QUERIES, query_vectors, strict=True):
            if len(vector) != expected_dimension:
                errors.append(
                    f"query vector dimension must be {expected_dimension}, "
                    f"got {len(vector)} for query={query}"
                )
                continue

            hits = search_qdrant(
                client=client,
                qdrant_url=qdrant_url,
                collection_name=collection_name,
                vector=vector,
                top_k=top_k,
            )

            query_errors = validate_hits(query=query, hits=hits)
            errors.extend(query_errors)

            query_results.append(
                {
                    "query": query,
                    "hit_count": len(hits),
                    "top_hit": safe_hit_preview(hits[0]) if hits else None,
                    "errors": query_errors,
                }
            )

    result = {
        "qdrant_url": qdrant_url,
        "collection_name": collection_name,
        "embedding_base_url": embedding_base_url,
        "embedding_model": embedding_model,
        "expected_dimension": expected_dimension,
        "top_k": top_k,
        "points_count": points_count if "points_count" in locals() else None,
        "query_count": len(TEST_QUERIES),
        "query_results": query_results,
        "errors": errors,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pprint(result)

    if errors:
        print("Logistics KB Qdrant retrieval check failed")
        return False

    print("Logistics KB Qdrant retrieval check passed")
    return True


def validate_hits(
    *,
    query: str,
    hits: list[dict[str, Any]],
) -> list[str]:
    """Validate retrieval hits."""

    errors: list[str] = []

    if not hits:
        return [f"{query}: no retrieval hits"]

    top_hit = hits[0]
    payload = top_hit.get("payload")

    if not isinstance(payload, dict):
        return [f"{query}: top hit payload must be dict"]

    if payload.get("module") != "logistics":
        errors.append(f"{query}: top hit module must be logistics")

    if payload.get("collection_name") != "logistics_kb_v1":
        errors.append(f"{query}: top hit collection_name must be logistics_kb_v1")

    if payload.get("allow_answer_reference") is not True:
        errors.append(f"{query}: allow_answer_reference must be true")

    if payload.get("allow_commitment_reference") is not False:
        errors.append(f"{query}: allow_commitment_reference must be false")

    if not payload.get("content"):
        errors.append(f"{query}: payload content is empty")

    if not str(payload.get("chunk_id") or "").startswith("logistics_qa_logi"):
        errors.append(f"{query}: chunk_id must start with logistics_qa_logi")

    return errors


def search_qdrant(
    *,
    client: httpx.Client,
    qdrant_url: str,
    collection_name: str,
    vector: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    """Search Qdrant collection."""

    payload = {
        "vector": vector,
        "limit": top_k,
        "with_payload": True,
        "with_vector": False,
        "filter": {
            "must": [
                {
                    "key": "module",
                    "match": {"value": "logistics"},
                },
                {
                    "key": "is_active",
                    "match": {"value": True},
                },
                {
                    "key": "allow_answer_reference",
                    "match": {"value": True},
                },
            ],
        },
    }

    response = client.post(
        f"{qdrant_url}/collections/{collection_name}/points/search",
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    result = data.get("result")

    if not isinstance(result, list):
        raise RuntimeError(f"unexpected Qdrant search response: {data}")

    return [
        item
        for item in result
        if isinstance(item, dict)
    ]


def embed_texts(
    *,
    client: httpx.Client,
    embedding_base_url: str,
    embedding_model: str,
    texts: list[str],
) -> list[list[float]]:
    """Call OpenAI-compatible embedding endpoint."""

    response = client.post(
        f"{embedding_base_url.rstrip('/')}/v1/embeddings",
        json={
            "model": embedding_model,
            "input": texts,
        },
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "embedding request failed: "
            f"status={response.status_code}, body={response.text[:1000]}"
        )

    data = response.json()
    raw_items = data.get("data")

    if not isinstance(raw_items, list):
        raise RuntimeError(f"unexpected embedding response: {data}")

    embeddings: list[list[float]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            raise RuntimeError(f"unexpected embedding item: {item}")

        embedding = item.get("embedding")

        if not isinstance(embedding, list):
            raise RuntimeError(f"missing embedding vector: {item}")

        embeddings.append([float(value) for value in embedding])

    return embeddings


def get_collection(
    *,
    client: httpx.Client,
    qdrant_url: str,
    collection_name: str,
) -> dict[str, Any]:
    """Get Qdrant collection info."""

    response = client.get(f"{qdrant_url}/collections/{collection_name}")
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected Qdrant collection response: {payload}")

    return result


def extract_vectors_config(
    collection_info: dict[str, Any],
) -> dict[str, Any]:
    """Extract vectors config from Qdrant collection info."""

    config = collection_info.get("config")

    if not isinstance(config, dict):
        return {}

    params = config.get("params")

    if not isinstance(params, dict):
        return {}

    vectors = params.get("vectors")

    if isinstance(vectors, dict):
        return vectors

    return {}


def safe_hit_preview(
    hit: dict[str, Any],
) -> dict[str, Any]:
    """Return safe hit preview."""

    payload = hit.get("payload")

    if not isinstance(payload, dict):
        payload = {}

    return {
        "id": hit.get("id"),
        "score": hit.get("score"),
        "payload": {
            key: payload.get(key)
            for key in (
                "chunk_id",
                "module",
                "collection_name",
                "source_type",
                "source_name",
                "summary",
                "risk_level",
                "handoff_required",
                "is_active",
                "allow_answer_reference",
                "allow_commitment_reference",
            )
        },
    }


def get_qdrant_url() -> str:
    """Build Qdrant URL from env."""

    explicit_url = os.getenv("QDRANT_URL", "").strip()

    if explicit_url:
        return explicit_url.rstrip("/")

    host = os.getenv("QDRANT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.getenv("QDRANT_PORT", "6333").strip() or "6333"

    return f"http://{host}:{port}"


def get_int_env(
    key: str,
    default: int,
) -> int:
    """Read integer env."""

    value = os.getenv(key, "").strip()

    if not value:
        return default

    return int(value)


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

    passed = check_logistics_kb_qdrant_retrieval()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())