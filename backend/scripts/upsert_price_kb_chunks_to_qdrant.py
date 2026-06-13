# ruff: noqa: E402,I001
"""Upsert Price KB chunks from PostgreSQL to Qdrant."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from pprint import pprint
from typing import Any, Final
from urllib import request

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory


COLLECTION_NAME: Final[str] = "price_kb_v1"
EXPECTED_COUNT: Final[int] = 50
EXPECTED_DIMENSION: Final[int] = 1024
DEFAULT_BATCH_SIZE: Final[int] = 8


def main() -> int:
    """Upsert Price KB chunks to Qdrant."""

    print("=" * 80)
    print("upserting Price KB chunks to Qdrant")

    set_required_env()

    errors: list[str] = []
    rows = load_price_rows_from_postgres()

    if len(rows) != EXPECTED_COUNT:
        errors.append(f"expected {EXPECTED_COUNT} db rows, got {len(rows)}")
        pprint({"errors": errors, "row_count": len(rows)})
        return 1

    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    qdrant_client = QdrantClient(url=qdrant_url)

    if not qdrant_client.collection_exists(collection_name=COLLECTION_NAME):
        errors.append(f"missing Qdrant collection: {COLLECTION_NAME}")
        pprint({"errors": errors})
        return 1

    batch_size = read_batch_size()
    upserted_count = 0

    for batch_rows in iter_batches(rows, batch_size):
        texts = [extract_text(row) for row in batch_rows]
        vectors = embed_texts(texts=texts)

        if len(vectors) != len(batch_rows):
            raise ValueError(
                f"embedding count mismatch: {len(vectors)} vs {len(batch_rows)}"
            )

        points = build_points(rows=batch_rows, vectors=vectors)

        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )
        upserted_count += len(points)

    qdrant_count = int(
        qdrant_client.count(
            collection_name=COLLECTION_NAME,
            exact=True,
        ).count
    )

    if qdrant_count != EXPECTED_COUNT:
        errors.append(
            f"expected {EXPECTED_COUNT} Qdrant points, got {qdrant_count}"
        )

    result: dict[str, Any] = {
        "collection_name": COLLECTION_NAME,
        "qdrant_url": qdrant_url,
        "db_row_count": len(rows),
        "upserted_count": upserted_count,
        "qdrant_count": qdrant_count,
        "embedding_dimension": EXPECTED_DIMENSION,
        "batch_size": batch_size,
        "first_chunk_id": rows[0].get("chunk_id") if rows else None,
        "last_chunk_id": rows[-1].get("chunk_id") if rows else None,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Price KB Qdrant upsert failed")
        return 1

    print("Price KB Qdrant upsert passed")
    return 0


def set_required_env() -> None:
    """Set required embedding env vars."""

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = str(EXPECTED_DIMENSION)
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    os.environ["EMBEDDING_MAX_RETRIES"] = "2"
    os.environ.setdefault("EMBEDDING_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))


def load_price_rows_from_postgres() -> list[dict[str, Any]]:
    """Load active Price KB rows from PostgreSQL."""

    session_factory = get_session_factory()

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT *
                FROM knowledge_chunks
                WHERE collection_name = :collection_name
                  AND chunk_id LIKE 'price_qa_price%%'
                  AND is_active = TRUE
                ORDER BY chunk_id
                """
            ),
            {"collection_name": COLLECTION_NAME},
        )

        return [dict(row) for row in result.mappings().all()]


def embed_texts(
    *,
    texts: list[str],
) -> list[list[float]]:
    """Embed texts through local TEI HTTP API."""

    base_url = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "120"))
    endpoint = f"{base_url}/embed"

    body = json.dumps({"inputs": texts}).encode("utf-8")

    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310
        raw_response = response.read().decode("utf-8")

    parsed = json.loads(raw_response)

    if not isinstance(parsed, list):
        raise ValueError("embedding response must be a list")

    vectors: list[list[float]] = []

    for index, item in enumerate(parsed):
        if not isinstance(item, list):
            raise ValueError(f"embedding item {index} must be a list")

        vector = [float(value) for value in item]
        vectors.append(vector)

    return vectors


def build_points(
    *,
    rows: list[dict[str, Any]],
    vectors: list[list[float]],
) -> list[PointStruct]:
    """Build Qdrant points."""

    points: list[PointStruct] = []

    for row, vector in zip(rows, vectors, strict=True):
        validate_vector(vector=vector, row=row)

        points.append(
            PointStruct(
                id=build_point_id(chunk_id=str(row["chunk_id"])),
                vector=vector,
                payload=build_payload(row=row),
            )
        )

    return points


def extract_text(
    row: dict[str, Any],
) -> str:
    """Extract text for embedding."""

    for key in ("chunk_text", "content"):
        value = row.get(key)

        if value is not None and str(value).strip():
            return str(value).strip()

    raise ValueError(f"{row.get('chunk_id')}: empty chunk text")


def build_payload(
    *,
    row: dict[str, Any],
) -> dict[str, Any]:
    """Build Qdrant payload from PostgreSQL row."""

    payload = parse_json_object(row.get("payload"))

    metadata_source = (
        row.get("metadata_json")
        if row.get("metadata_json") is not None
        else row.get("metadata")
    )
    metadata = parse_json_object(metadata_source)

    payload.update(metadata)
    payload.update(
        {
            "chunk_id": row.get("chunk_id"),
            "doc_id": row.get("doc_id"),
            "doc_title": row.get("doc_title"),
            "content": extract_text(row),
            "summary": row.get("summary"),
            "collection_name": COLLECTION_NAME,
            "module": "price",
            "source_type": row.get("source_type", "qa_pair"),
            "source_name": row.get("source_name", "price_questions.xlsx"),
            "source_row_index": row.get("source_row_index"),
            "risk_level": row.get("risk_level"),
            "is_verified": row.get("is_verified"),
            "source": "qdrant",
            "allow_answer_reference": True,
            "allow_commitment_reference": False,
        }
    )

    return payload


def parse_json_object(
    value: Any,
) -> dict[str, Any]:
    """Parse JSON object from DB value."""

    if isinstance(value, dict):
        return {
            str(key): item_value
            for key, item_value in value.items()
        }

    if value is None:
        return {}

    text_value = str(value).strip()

    if not text_value:
        return {}

    parsed = json.loads(text_value)

    if not isinstance(parsed, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in parsed.items()
    }


def build_point_id(
    *,
    chunk_id: str,
) -> str:
    """Build deterministic Qdrant UUID point id."""

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{COLLECTION_NAME}:{chunk_id}"))


def validate_vector(
    *,
    vector: list[float],
    row: dict[str, Any],
) -> None:
    """Validate vector dimension."""

    if len(vector) != EXPECTED_DIMENSION:
        raise ValueError(
            f"{row.get('chunk_id')}: vector dimension must be "
            f"{EXPECTED_DIMENSION}, got {len(vector)}"
        )


def read_batch_size() -> int:
    """Read embedding batch size."""

    value = os.getenv("EMBEDDING_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)).strip()

    if not value:
        return DEFAULT_BATCH_SIZE

    batch_size = int(value)

    if batch_size <= 0:
        return DEFAULT_BATCH_SIZE

    return batch_size


def iter_batches(
    rows: list[dict[str, Any]],
    batch_size: int,
) -> list[list[dict[str, Any]]]:
    """Return row batches."""

    return [
        rows[index : index + batch_size]
        for index in range(0, len(rows), batch_size)
    ]


if __name__ == "__main__":
    raise SystemExit(main())