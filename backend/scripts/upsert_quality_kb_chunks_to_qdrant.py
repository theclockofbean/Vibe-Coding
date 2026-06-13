# ruff: noqa: E402,I001
"""Embed Quality KB chunks and upsert vectors into Qdrant quality_kb_v1."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

import httpx
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import URL, Engine

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.real_embedding import (
    OpenAICompatibleEmbeddingClient,
    RealEmbeddingConfig,
    RealEmbeddingError,
)


ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

PROBE_OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "embedding"
    / "embedding_probe_result.json"
)

KNOWLEDGE_CHUNKS_TABLE: Final[str] = "knowledge_chunks"
DEFAULT_COLLECTION_NAME: Final[str] = "quality_kb_v1"
DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_BATCH_SIZE: Final[int] = 8


def upsert_quality_chunks_to_qdrant() -> bool:
    """Embed quality chunks and upsert to Qdrant."""

    print("=" * 80)
    print("upserting quality KB chunks into Qdrant")

    load_env_file(ENV_FILE)

    collection_name = get_quality_collection_name()
    qdrant_url = get_qdrant_url()
    probe_result = load_probe_result()
    expected_dimension = get_expected_dimension(probe_result)

    result: dict[str, Any] = {
        "collection_name": collection_name,
        "qdrant_url": qdrant_url,
        "probe_status": probe_result.get("status"),
        "expected_dimension": expected_dimension,
        "fetched_chunk_count": 0,
        "embedded_vector_count": 0,
        "upserted_point_count": 0,
        "collection_points_count_after": None,
        "errors": [],
    }

    errors: list[str] = result["errors"]

    if probe_result.get("status") != "passed":
        errors.append("embedding probe result is not passed")

    if expected_dimension is None:
        errors.append("expected embedding dimension is missing")

    if errors:
        pprint(result)
        return False

    assert expected_dimension is not None

    try:
        verify_qdrant_collection(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            expected_dimension=expected_dimension,
        )

        engine = create_database_engine()
        table = reflect_knowledge_chunks_table(engine)
        chunks = fetch_quality_chunks(engine=engine, table=table)

        result["fetched_chunk_count"] = len(chunks)

        if not chunks:
            errors.append("no quality chunks found in PostgreSQL")
            pprint(result)
            return False

        client = OpenAICompatibleEmbeddingClient(
            config=RealEmbeddingConfig.from_env()
        )

        batch_size = get_batch_size()
        upserted_total = 0
        embedded_total = 0

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            texts = [str(item["content"]) for item in batch]

            vectors = client.embed_texts(texts)
            embedded_total += len(vectors)

            points = build_qdrant_points(
                chunks=batch,
                vectors=vectors,
                expected_dimension=expected_dimension,
            )

            upsert_points(
                qdrant_url=qdrant_url,
                collection_name=collection_name,
                points=points,
            )

            upserted_total += len(points)

            print(
                f"upserted batch: start={batch_start}, "
                f"size={len(points)}, total={upserted_total}"
            )

        result["embedded_vector_count"] = embedded_total
        result["upserted_point_count"] = upserted_total

        collection_payload = get_collection(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
        )
        result["collection_points_count_after"] = collection_payload.get(
            "points_count"
        )

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        pprint(result)
        return False

    pprint(result)

    if result["upserted_point_count"] != result["fetched_chunk_count"]:
        print("quality KB Qdrant upsert check failed")
        return False

    if result["collection_points_count_after"] is not None:
        if int(result["collection_points_count_after"]) < int(
            result["fetched_chunk_count"]
        ):
            print("quality KB Qdrant point count check failed")
            return False

    print("quality KB Qdrant upsert check passed")
    return True


def create_database_engine() -> Engine:
    """Create SQLAlchemy engine."""

    database_url = os.getenv("DATABASE_URL", "").strip()

    if database_url:
        return create_engine(database_url)

    database_host = os.getenv("DATABASE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    database_port_text = os.getenv("DATABASE_PORT", "5432").strip() or "5432"
    database_name = os.getenv("DATABASE_NAME", "ai_knowledge_agent").strip()
    database_user = os.getenv("DATABASE_USER", "ai_kb_app").strip()
    database_password = os.getenv("DATABASE_PASSWORD", "")

    if not database_password:
        raise RuntimeError("DATABASE_PASSWORD is missing")

    url = URL.create(
        drivername="postgresql+psycopg",
        username=database_user,
        password=database_password,
        host=database_host,
        port=int(database_port_text),
        database=database_name,
    )

    return create_engine(url)


def reflect_knowledge_chunks_table(
    engine: Engine,
) -> Table:
    """Reflect knowledge_chunks table."""

    metadata = MetaData()
    return Table(
        KNOWLEDGE_CHUNKS_TABLE,
        metadata,
        autoload_with=engine,
    )


def fetch_quality_chunks(
    *,
    engine: Engine,
    table: Table,
) -> list[dict[str, Any]]:
    """Fetch quality chunks from PostgreSQL."""

    required_columns = [
        "chunk_id",
        "collection_name",
        "source_type",
        "source_name",
        "source_uri",
        "doc_id",
        "doc_title",
        "chunk_index",
        "module",
        "sku_scope",
        "intent_scope",
        "content",
        "content_hash",
        "summary",
        "language",
        "risk_level",
        "is_active",
        "is_verified",
        "allow_answer_reference",
        "allow_commitment_reference",
        "embedding_model",
        "embedding_dimension",
        "qdrant_point_id",
        "version",
        "metadata",
    ]

    missing = [
        column_name
        for column_name in required_columns
        if column_name not in table.c
    ]

    if missing:
        raise RuntimeError(f"knowledge_chunks missing columns: {missing}")

    statement = (
        select(*[table.c[column_name] for column_name in required_columns])
        .where(
            table.c["module"] == "quality",
            table.c["collection_name"] == get_quality_collection_name(),
            table.c["is_active"].is_(True),
            table.c["allow_answer_reference"].is_(True),
        )
        .order_by(table.c["chunk_index"].asc(), table.c["chunk_id"].asc())
    )

    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def build_qdrant_points(
    *,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
    expected_dimension: int,
) -> list[dict[str, Any]]:
    """Build Qdrant points."""

    if len(chunks) != len(vectors):
        raise RuntimeError(
            f"chunk/vector count mismatch: chunks={len(chunks)}, "
            f"vectors={len(vectors)}"
        )

    points: list[dict[str, Any]] = []

    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != expected_dimension:
            raise RuntimeError(
                f"vector dimension mismatch for {chunk['chunk_id']}: "
                f"expected={expected_dimension}, actual={len(vector)}"
            )

        qdrant_point_id = str(chunk["qdrant_point_id"])

        if not qdrant_point_id:
            raise RuntimeError(f"missing qdrant_point_id for {chunk['chunk_id']}")

        points.append(
            {
                "id": qdrant_point_id,
                "vector": vector,
                "payload": build_qdrant_payload(chunk),
            }
        )

    return points


def build_qdrant_payload(
    chunk: dict[str, Any],
) -> dict[str, Any]:
    """Build safe Qdrant payload."""

    payload = {
        "chunk_id": chunk["chunk_id"],
        "collection_name": chunk["collection_name"],
        "module": chunk["module"],
        "source_type": chunk["source_type"],
        "source_name": chunk["source_name"],
        "source_uri": chunk["source_uri"],
        "doc_id": chunk["doc_id"],
        "doc_title": chunk["doc_title"],
        "chunk_index": chunk["chunk_index"],
        "sku_scope": chunk["sku_scope"],
        "intent_scope": chunk["intent_scope"],
        "content": chunk["content"],
        "content_hash": chunk["content_hash"],
        "summary": chunk["summary"],
        "language": chunk["language"],
        "risk_level": chunk["risk_level"],
        "is_active": chunk["is_active"],
        "is_verified": chunk["is_verified"],
        "allow_answer_reference": chunk["allow_answer_reference"],
        "allow_commitment_reference": chunk["allow_commitment_reference"],
        "embedding_model": chunk["embedding_model"],
        "embedding_dimension": chunk["embedding_dimension"],
        "version": chunk["version"],
        "metadata": chunk["metadata"],
    }

    serialized = json.dumps(payload, ensure_ascii=False)
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip()

    if api_key and api_key in serialized:
        raise RuntimeError("EMBEDDING_API_KEY would leak into Qdrant payload")

    return payload


def upsert_points(
    *,
    qdrant_url: str,
    collection_name: str,
    points: list[dict[str, Any]],
) -> None:
    """Upsert points into Qdrant."""

    response = httpx.put(
        f"{qdrant_url}/collections/{collection_name}/points",
        params={"wait": "true"},
        json={
            "points": points,
        },
        timeout=180.0,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant upsert returned HTTP {response.status_code}: "
            f"{response.text[:800]}"
        )


def verify_qdrant_collection(
    *,
    qdrant_url: str,
    collection_name: str,
    expected_dimension: int,
) -> None:
    """Verify Qdrant collection exists and vector size matches."""

    collection = get_collection(
        qdrant_url=qdrant_url,
        collection_name=collection_name,
    )

    config = collection.get("config")

    if not isinstance(config, dict):
        raise RuntimeError("Qdrant collection config missing")

    params = config.get("params")

    if not isinstance(params, dict):
        raise RuntimeError("Qdrant collection config.params missing")

    vectors = params.get("vectors")

    if not isinstance(vectors, dict):
        raise RuntimeError("Qdrant collection vectors config missing")

    actual_size = vectors.get("size")
    actual_distance = vectors.get("distance")

    if actual_size != expected_dimension:
        raise RuntimeError(
            f"Qdrant vector size mismatch: "
            f"expected={expected_dimension}, actual={actual_size}"
        )

    if str(actual_distance).lower() != "cosine":
        raise RuntimeError(
            f"Qdrant distance must be Cosine, got {actual_distance}"
        )


def get_collection(
    *,
    qdrant_url: str,
    collection_name: str,
) -> dict[str, Any]:
    """Get Qdrant collection."""

    response = httpx.get(
        f"{qdrant_url}/collections/{collection_name}",
        timeout=30.0,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant collection get returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("Qdrant response must be object")

    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError("Qdrant response result must be object")

    return {
        str(key): value
        for key, value in result.items()
    }


def load_probe_result() -> dict[str, Any]:
    """Load embedding probe result."""

    if not PROBE_OUTPUT_FILE.exists():
        return {}

    data = json.loads(PROBE_OUTPUT_FILE.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        return {}

    return {
        str(key): value
        for key, value in data.items()
    }


def get_expected_dimension(
    probe_result: dict[str, Any],
) -> int | None:
    """Get expected embedding dimension."""

    value = probe_result.get("vector_dimension")

    if isinstance(value, int) and value > 0:
        return value

    env_value = os.getenv("EMBEDDING_DIMENSION", "").strip()

    if env_value.isdigit():
        return int(env_value)

    return None


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


def get_batch_size() -> int:
    """Return embedding batch size."""

    value = os.getenv("EMBEDDING_BATCH_SIZE", "").strip()

    if value.isdigit():
        return max(1, min(int(value), 32))

    return DEFAULT_BATCH_SIZE


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

    try:
        passed = upsert_quality_chunks_to_qdrant()
    except RealEmbeddingError as exc:
        print(f"quality KB Qdrant upsert embedding failed: {exc}")
        return 1
    except Exception as exc:
        print(
            "quality KB Qdrant upsert crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())