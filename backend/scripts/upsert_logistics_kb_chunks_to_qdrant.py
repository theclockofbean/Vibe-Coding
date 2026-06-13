# ruff: noqa: E402,I001
"""Upsert Logistics KB vectors to Qdrant logistics_kb_v1."""

from __future__ import annotations

import json
import os
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import httpx
import psycopg


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "logistics"
    / "logistics_kb_qdrant_upsert_result.json"
)

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "logistics_kb_v1"
DEFAULT_EMBEDDING_BASE_URL: Final[str] = "http://127.0.0.1:8088"
DEFAULT_EMBEDDING_MODEL: Final[str] = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIMENSION: Final[int] = 1024
EXPECTED_CHUNK_COUNT: Final[int] = 50


def upsert_logistics_kb_chunks_to_qdrant() -> bool:
    """Upsert Logistics KB chunk vectors to Qdrant."""

    print("=" * 80)
    print("upserting Logistics KB chunks to Qdrant")

    load_env_file(ENV_FILE)
    os.environ["PGCLIENTENCODING"] = "UTF8"

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

    errors: list[str] = []

    with psycopg.connect(
        host=get_required_env("DATABASE_HOST", default="127.0.0.1"),
        port=get_required_env("DATABASE_PORT", default="5432"),
        dbname=get_required_env("DATABASE_NAME"),
        user=get_required_env("DATABASE_USER"),
        password=get_required_env("DATABASE_PASSWORD"),
    ) as connection:
        chunks = fetch_logistics_chunks(connection)

    if len(chunks) != EXPECTED_CHUNK_COUNT:
        errors.append(
            f"fetched chunk count must be {EXPECTED_CHUNK_COUNT}, got {len(chunks)}"
        )

    if errors:
        result = {
            "collection_name": collection_name,
            "fetched_chunk_count": len(chunks),
            "expected_chunk_count": EXPECTED_CHUNK_COUNT,
            "errors": errors,
        }
        pprint(result)
        return False

    with httpx.Client(timeout=120.0) as client:
        verify_qdrant_collection(
            client=client,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            expected_dimension=expected_dimension,
        )

        embeddings = embed_texts(
            client=client,
            embedding_base_url=embedding_base_url,
            embedding_model=embedding_model,
            texts=[chunk["content"] for chunk in chunks],
        )

        if len(embeddings) != len(chunks):
            errors.append(
                f"embedding count must equal chunk count, "
                f"got embeddings={len(embeddings)}, chunks={len(chunks)}"
            )

        for index, vector in enumerate(embeddings):
            if len(vector) != expected_dimension:
                errors.append(
                    f"embedding[{index}] dimension must be {expected_dimension}, "
                    f"got {len(vector)}"
                )

        if errors:
            result = {
                "collection_name": collection_name,
                "fetched_chunk_count": len(chunks),
                "embedded_vector_count": len(embeddings),
                "expected_dimension": expected_dimension,
                "errors": errors,
            }
            pprint(result)
            return False

        points = build_qdrant_points(
            chunks=chunks,
            embeddings=embeddings,
            collection_name=collection_name,
        )

        upsert_points(
            client=client,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            points=points,
        )

        collection_info = get_collection(
            client=client,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
        )

    points_count = collection_info.get("points_count")

    result = {
        "qdrant_url": qdrant_url,
        "collection_name": collection_name,
        "embedding_base_url": embedding_base_url,
        "embedding_model": embedding_model,
        "expected_dimension": expected_dimension,
        "fetched_chunk_count": len(chunks),
        "embedded_vector_count": len(embeddings),
        "upserted_point_count": len(points),
        "collection_points_count_after": points_count,
        "sample_point": safe_point_preview(points[0]) if points else None,
        "errors": errors,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pprint(result)

    if points_count != EXPECTED_CHUNK_COUNT:
        print("Logistics KB Qdrant upsert check failed")
        return False

    print("Logistics KB Qdrant upsert check passed")
    return True


def fetch_logistics_chunks(
    connection: psycopg.Connection[Any],
) -> list[dict[str, Any]]:
    """Fetch logistics chunks from PostgreSQL."""

    query = """
        SELECT *
        FROM knowledge_chunks
        WHERE chunk_id LIKE 'logistics_qa_logi%%'
          AND collection_name = 'logistics_kb_v1'
          AND is_active = TRUE
        ORDER BY chunk_id
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        assert cursor.description is not None
        column_names = [description.name for description in cursor.description]

    chunks: list[dict[str, Any]] = []

    for row in rows:
        item = dict(zip(column_names, row, strict=True))
        content = str(item.get("content") or "").strip()
        point_id = str(item.get("qdrant_point_id") or "").strip()

        if not content:
            raise RuntimeError(f"empty content for chunk_id={item.get('chunk_id')}")

        if not point_id:
            raise RuntimeError(
                f"empty qdrant_point_id for chunk_id={item.get('chunk_id')}"
            )

        chunks.append(item)

    return chunks


def embed_texts(
    *,
    client: httpx.Client,
    embedding_base_url: str,
    embedding_model: str,
    texts: list[str],
) -> list[list[float]]:
    """Call OpenAI-compatible embedding endpoint in small batches."""

    url = f"{embedding_base_url.rstrip('/')}/v1/embeddings"
    batch_size = get_int_env("EMBEDDING_BATCH_SIZE", 8)

    if batch_size <= 0:
        raise RuntimeError(f"EMBEDDING_BATCH_SIZE must be positive, got {batch_size}")

    embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start : start + batch_size]
        payload = {
            "model": embedding_model,
            "input": batch_texts,
        }

        response = client.post(url, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(
                "embedding request failed: "
                f"status={response.status_code}, "
                f"batch_start={start}, "
                f"batch_size={len(batch_texts)}, "
                f"body={response.text[:1000]}"
            )

        data = response.json()
        raw_items = data.get("data")

        if not isinstance(raw_items, list):
            raise RuntimeError(f"unexpected embedding response: {data}")

        for item in raw_items:
            if not isinstance(item, dict):
                raise RuntimeError(f"unexpected embedding item: {item}")

            embedding = item.get("embedding")

            if not isinstance(embedding, list):
                raise RuntimeError(f"missing embedding vector: {item}")

            embeddings.append([float(value) for value in embedding])

    return embeddings


def build_qdrant_points(
    *,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    collection_name: str,
) -> list[dict[str, Any]]:
    """Build Qdrant points."""

    points: list[dict[str, Any]] = []

    for chunk, vector in zip(chunks, embeddings, strict=True):
        point_id = str(chunk["qdrant_point_id"])
        payload = build_payload(
            chunk=chunk,
            collection_name=collection_name,
        )

        points.append(
            {
                "id": point_id,
                "vector": vector,
                "payload": payload,
            }
        )

    return points


def build_payload(
    *,
    chunk: dict[str, Any],
    collection_name: str,
) -> dict[str, Any]:
    """Build Qdrant payload from PostgreSQL chunk row."""

    metadata = chunk.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    payload = {
        "chunk_id": chunk.get("chunk_id"),
        "doc_id": chunk.get("doc_id"),
        "doc_title": chunk.get("doc_title"),
        "summary": chunk.get("summary"),
        "content": chunk.get("content"),
        "module": "logistics",
        "source": "qdrant",
        "source_type": chunk.get("source_type"),
        "source_name": chunk.get("source_name"),
        "source_row_id": chunk.get("source_row_id"),
        "source_row_index": chunk.get("source_row_index"),
        "chunk_index": chunk.get("chunk_index"),
        "collection_name": collection_name,
        "qdrant_collection_name": collection_name,
        "qdrant_point_id": chunk.get("qdrant_point_id"),
        "risk_level": chunk.get("risk_level"),
        "risk_flags": to_jsonable(chunk.get("risk_flags")),
        "related_sku_ids": to_jsonable(chunk.get("related_sku_ids")),
        "sku_scope": to_jsonable(chunk.get("sku_scope")),
        "intent_scope": to_jsonable(chunk.get("intent_scope")),
        "verification_status": chunk.get("verification_status"),
        "is_verified": chunk.get("is_verified"),
        "is_active": chunk.get("is_active"),
        "handoff_required": chunk.get("handoff_required"),
        "allow_answer_reference": chunk.get("allow_answer_reference"),
        "allow_commitment_reference": chunk.get("allow_commitment_reference"),
        "metadata": to_jsonable(metadata),
    }

    return {
        key: to_jsonable(value)
        for key, value in payload.items()
        if value is not None
    }


def upsert_points(
    *,
    client: httpx.Client,
    qdrant_url: str,
    collection_name: str,
    points: list[dict[str, Any]],
) -> None:
    """Upsert points to Qdrant."""

    response = client.put(
        f"{qdrant_url}/collections/{collection_name}/points?wait=true",
        json={"points": points},
    )
    response.raise_for_status()
    payload = response.json()

    status = payload.get("status")
    result = payload.get("result")

    if status != "ok" and not isinstance(result, dict):
        raise RuntimeError(f"unexpected Qdrant upsert response: {payload}")


def verify_qdrant_collection(
    *,
    client: httpx.Client,
    qdrant_url: str,
    collection_name: str,
    expected_dimension: int,
) -> None:
    """Verify Qdrant collection config."""

    collection_info = get_collection(
        client=client,
        qdrant_url=qdrant_url,
        collection_name=collection_name,
    )

    vectors = extract_vectors_config(collection_info)
    actual_size = vectors.get("size")
    actual_distance = vectors.get("distance")

    if actual_size != expected_dimension:
        raise RuntimeError(
            f"collection vector size must be {expected_dimension}, got {actual_size}"
        )

    if str(actual_distance).lower() != "cosine":
        raise RuntimeError(
            f"collection distance must be Cosine, got {actual_distance}"
        )


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


def safe_point_preview(
    point: dict[str, Any],
) -> dict[str, Any]:
    """Return safe point preview without vector."""

    payload = point.get("payload")

    if not isinstance(payload, dict):
        payload = {}

    return {
        "id": point.get("id"),
        "payload": {
            key: payload.get(key)
            for key in (
                "chunk_id",
                "module",
                "collection_name",
                "source_type",
                "source_name",
                "risk_level",
                "is_active",
                "allow_answer_reference",
                "allow_commitment_reference",
            )
        },
    }


def to_jsonable(
    value: object,
) -> object:
    """Convert DB value to JSON-compatible value."""

    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item_value)
            for key, item_value in value.items()
        }

    if isinstance(value, list | tuple | set):
        return [to_jsonable(item) for item in value]

    return value


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


def get_required_env(
    key: str,
    *,
    default: str | None = None,
) -> str:
    """Read required env var."""

    value = os.getenv(key, "").strip()

    if value:
        return value

    if default is not None:
        return default

    raise RuntimeError(f"missing required env var: {key}")


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
    """Run script."""

    passed = upsert_logistics_kb_chunks_to_qdrant()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())