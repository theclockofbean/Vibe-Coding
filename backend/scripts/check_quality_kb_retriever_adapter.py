# ruff: noqa: E402,I001
"""Check QualityKBQdrantRetriever adapter."""

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

from app.agent.rag.quality_kb_retriever import QualityKBQdrantRetriever


ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

TEST_QUERIES: Final[tuple[str, ...]] = (
    "SKU001 这款铝合金6061材质质量怎么样？",
    "SKU001 阳极氧化黑色表面处理有什么品质说明？",
    "这个球头有没有检测报告？",
)


def check_quality_kb_retriever_adapter() -> bool:
    """Check retriever adapter."""

    print("=" * 80)
    print("checking QualityKBQdrantRetriever adapter")

    load_env_file(ENV_FILE)

    retriever = QualityKBQdrantRetriever.from_env()

    result: dict[str, Any] = {
        "query_count": len(TEST_QUERIES),
        "results": [],
        "errors": [],
    }

    errors: list[str] = result["errors"]

    for query in TEST_QUERIES:
        hits = retriever.retrieve(query)
        payloads = retriever.retrieve_payloads(query)

        query_errors: list[str] = []

        query_result: dict[str, Any] = {
            "query": query,
            "hit_count": len(hits),
            "payload_count": len(payloads),
            "top_hit": safe_hit_preview(hits[0]) if hits else None,
            "top_payload": safe_payload_preview(payloads[0]) if payloads else None,
            "errors": query_errors,
        }

        if not hits:
            query_errors.append("no hits returned")

        if len(hits) != len(payloads):
            query_errors.append("hit/payload count mismatch")

        if hits:
            top_hit = hits[0]

            if not top_hit.chunk_id:
                query_errors.append("top hit chunk_id is empty")

            if not top_hit.content:
                query_errors.append("top hit content is empty")

            if top_hit.allow_answer_reference is not True:
                query_errors.append("top hit allow_answer_reference must be true")

            if top_hit.allow_commitment_reference is not False:
                query_errors.append(
                    "top hit allow_commitment_reference must be false"
                )

        if payloads:
            top_payload = payloads[0]

            if top_payload.get("module") != "quality":
                query_errors.append("top payload module must be quality")

            if top_payload.get("collection_name") != "quality_kb_v1":
                query_errors.append(
                    "top payload collection_name must be quality_kb_v1"
                )

            if top_payload.get("source") != "qdrant":
                query_errors.append("top payload source must be qdrant")

        if query_errors:
            errors.extend(
                f"{query}: {error}"
                for error in query_errors
            )

        result["results"].append(query_result)

    serialized = json.dumps(result, ensure_ascii=False)
    embedding_api_key = os.getenv("EMBEDDING_API_KEY", "").strip()

    if embedding_api_key and embedding_api_key in serialized:
        errors.append("EMBEDDING_API_KEY leaked into adapter check result")

    pprint(result)

    if errors:
        print("QualityKBQdrantRetriever adapter check failed")
        return False

    print("QualityKBQdrantRetriever adapter check passed")
    return True


def safe_hit_preview(
    hit: Any,
) -> dict[str, Any]:
    """Return safe hit preview."""

    return {
        "chunk_id": hit.chunk_id,
        "score": hit.score,
        "doc_id": hit.doc_id,
        "doc_title": hit.doc_title,
        "risk_level": hit.risk_level,
        "sku_scope": hit.sku_scope,
        "intent_scope": hit.intent_scope,
        "allow_answer_reference": hit.allow_answer_reference,
        "allow_commitment_reference": hit.allow_commitment_reference,
        "summary": hit.summary,
    }


def safe_payload_preview(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Return safe payload preview."""

    allowed_keys = {
        "chunk_id",
        "summary",
        "score",
        "source",
        "source_type",
        "source_name",
        "doc_id",
        "doc_title",
        "module",
        "collection_name",
        "risk_level",
        "sku_scope",
        "intent_scope",
        "is_verified",
        "allow_answer_reference",
        "allow_commitment_reference",
    }

    return {
        key: value
        for key, value in payload.items()
        if key in allowed_keys
    }


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
        passed = check_quality_kb_retriever_adapter()
    except Exception as exc:
        print(
            "QualityKBQdrantRetriever adapter check crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())