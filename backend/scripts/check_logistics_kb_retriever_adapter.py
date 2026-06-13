# ruff: noqa: E402,I001
"""Check LogisticsKBQdrantRetriever adapter."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.logistics_kb_retriever import LogisticsKBQdrantRetriever


ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"
OUTPUT_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "parsed"
    / "logistics"
    / "logistics_kb_retriever_adapter_check_result.json"
)

TEST_QUERIES: Final[tuple[str, ...]] = (
    "SKU001今天拍什么时候发货？",
    "发浙江大概几天能到？",
    "偏远地区运费怎么确认？",
)


def check_logistics_kb_retriever_adapter() -> bool:
    """Check LogisticsKBQdrantRetriever adapter."""

    print("=" * 80)
    print("checking LogisticsKBQdrantRetriever adapter")

    load_env_file(ENV_FILE)
    set_required_env()

    retriever = LogisticsKBQdrantRetriever.from_env()

    errors: list[str] = []
    query_results: list[dict[str, Any]] = []

    for query in TEST_QUERIES:
        query_errors: list[str] = []
        hits = retriever.retrieve(query)
        payloads = retriever.retrieve_chunks(query)

        if not hits:
            query_errors.append("hits is empty")

        if not payloads:
            query_errors.append("retrieved chunk payloads is empty")

        if hits:
            top_hit = hits[0]

            if top_hit.payload.get("module") != "logistics":
                query_errors.append("top hit module must be logistics")

            if top_hit.payload.get("collection_name") != "logistics_kb_v1":
                query_errors.append("top hit collection_name must be logistics_kb_v1")

            if top_hit.payload.get("allow_answer_reference") is not True:
                query_errors.append("top hit allow_answer_reference must be true")

            if top_hit.payload.get("allow_commitment_reference") is not False:
                query_errors.append("top hit allow_commitment_reference must be false")

        if payloads:
            top_payload = payloads[0]

            if top_payload.get("module") != "logistics":
                query_errors.append("top payload module must be logistics")

            if top_payload.get("source") != "qdrant":
                query_errors.append("top payload source must be qdrant")

            if top_payload.get("collection_name") != "logistics_kb_v1":
                query_errors.append("top payload collection_name must be logistics_kb_v1")

            if top_payload.get("allow_answer_reference") is not True:
                query_errors.append("top payload allow_answer_reference must be true")

            if top_payload.get("allow_commitment_reference") is not False:
                query_errors.append("top payload allow_commitment_reference must be false")

            if not top_payload.get("content"):
                query_errors.append("top payload content is empty")

        errors.extend(f"{query}: {error}" for error in query_errors)

        query_results.append(
            {
                "query": query,
                "hit_count": len(hits),
                "payload_count": len(payloads),
                "top_hit": safe_hit_preview(hits[0]) if hits else None,
                "top_payload": safe_payload_preview(payloads[0]) if payloads else None,
                "errors": query_errors,
            }
        )

    result = {
        "collection_name": retriever.collection_name,
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
        print("LogisticsKBQdrantRetriever adapter check failed")
        return False

    print("LogisticsKBQdrantRetriever adapter check passed")
    return True


def safe_hit_preview(hit: object) -> dict[str, Any]:
    """Return safe hit preview."""

    payload = getattr(hit, "payload", {})

    if not isinstance(payload, dict):
        payload = {}

    return {
        "point_id": getattr(hit, "point_id", None),
        "score": getattr(hit, "score", None),
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
                "allow_answer_reference",
                "allow_commitment_reference",
            )
        },
    }


def safe_payload_preview(payload: object) -> dict[str, Any]:
    """Return safe retrieved payload preview."""

    if not isinstance(payload, dict):
        return {}

    return {
        key: payload.get(key)
        for key in (
            "chunk_id",
            "module",
            "source",
            "collection_name",
            "source_type",
            "source_name",
            "summary",
            "risk_level",
            "allow_answer_reference",
            "allow_commitment_reference",
        )
    }


def set_required_env() -> None:
    """Set required env vars for adapter check."""

    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    os.environ["EMBEDDING_MAX_RETRIES"] = "2"
    os.environ["LOGISTICS_KB_TOP_K"] = "5"


def load_env_file(env_file: Path) -> None:
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

    passed = check_logistics_kb_retriever_adapter()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())