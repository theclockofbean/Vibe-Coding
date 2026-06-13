"""Real Quality KB retriever backed by bge-m3 embeddings and Qdrant."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

from app.agent.rag.real_embedding import (
    OpenAICompatibleEmbeddingClient,
    RealEmbeddingConfig,
)

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "quality_kb_v1"
DEFAULT_TOP_K: Final[int] = 5


@dataclass(frozen=True)
class QualityKBHit:
    """One retrieved Quality KB hit."""

    point_id: str
    score: float | None
    chunk_id: str
    content: str
    summary: str
    doc_id: str
    doc_title: str
    source_name: str
    source_uri: str
    risk_level: str
    sku_scope: list[str]
    intent_scope: list[str]
    is_verified: bool
    allow_answer_reference: bool
    allow_commitment_reference: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_retrieved_chunk_payload(self) -> dict[str, Any]:
        """Return workflow-compatible retrieved chunk payload."""

        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "summary": self.summary,
            "score": self.score,
            "source": "qdrant",
            "source_type": "rag_chunk",
            "source_name": self.source_name,
            "source_uri": self.source_uri,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "module": "quality",
            "collection_name": get_quality_collection_name(),
            "risk_level": self.risk_level,
            "sku_scope": self.sku_scope,
            "intent_scope": self.intent_scope,
            "is_verified": self.is_verified,
            "allow_answer_reference": self.allow_answer_reference,
            "allow_commitment_reference": self.allow_commitment_reference,
            "metadata": {
                **self.metadata,
                "retriever": "real_quality_kb_retriever",
                "embedding_model": get_embedding_model(),
                "collection_name": get_quality_collection_name(),
            },
        }


@dataclass
class QualityKBQdrantRetriever:
    """Retrieve quality KB chunks from Qdrant."""

    qdrant_url: str
    collection_name: str
    embedding_client: OpenAICompatibleEmbeddingClient
    top_k: int = DEFAULT_TOP_K

    @classmethod
    def from_env(cls) -> QualityKBQdrantRetriever:
        """Build retriever from environment."""

        return cls(
            qdrant_url=get_qdrant_url(),
            collection_name=get_quality_collection_name(),
            embedding_client=OpenAICompatibleEmbeddingClient(
                config=RealEmbeddingConfig.from_env()
            ),
            top_k=get_quality_top_k(),
        )

    def retrieve(
        self,
        query: str,
    ) -> list[QualityKBHit]:
        """Retrieve quality KB hits."""

        query_text = query.strip()

        if not query_text:
            return []

        vector = self.embedding_client.embed_texts([query_text])[0]

        raw_hits = self._search_qdrant(vector)
        hits = [
            hit
            for hit in (build_quality_hit(raw_hit) for raw_hit in raw_hits)
            if hit is not None
        ]

        return hits

    def retrieve_payloads(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """Retrieve workflow-compatible payloads."""

        return [
            hit.to_retrieved_chunk_payload()
            for hit in self.retrieve(query)
        ]

    def _search_qdrant(
        self,
        vector: list[float],
    ) -> list[dict[str, Any]]:
        """Search Qdrant."""

        filter_payload = {
            "must": [
                {
                    "key": "module",
                    "match": {
                        "value": "quality",
                    },
                },
                {
                    "key": "is_active",
                    "match": {
                        "value": True,
                    },
                },
                {
                    "key": "allow_answer_reference",
                    "match": {
                        "value": True,
                    },
                },
            ]
        }

        search_payload = {
            "vector": vector,
            "filter": filter_payload,
            "limit": self.top_k,
            "with_payload": True,
            "with_vector": False,
        }

        response = httpx.post(
            f"{self.qdrant_url}/collections/{self.collection_name}/points/search",
            json=search_payload,
            timeout=60.0,
        )

        if response.status_code in {404, 405}:
            query_payload = {
                "query": vector,
                "filter": filter_payload,
                "limit": self.top_k,
                "with_payload": True,
                "with_vector": False,
            }

            response = httpx.post(
                f"{self.qdrant_url}/collections/{self.collection_name}/points/query",
                json=query_payload,
                timeout=60.0,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Qdrant quality search failed: HTTP {response.status_code}: "
                f"{response.text[:800]}"
            )

        payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError("Qdrant search response must be JSON object")

        result = payload.get("result")

        if isinstance(result, dict) and isinstance(result.get("points"), list):
            return normalize_raw_hits(result["points"])

        if isinstance(result, list):
            return normalize_raw_hits(result)

        raise RuntimeError("Unsupported Qdrant search response shape")


def build_quality_hit(
    raw_hit: dict[str, Any],
) -> QualityKBHit | None:
    """Build one QualityKBHit from Qdrant hit."""

    payload = raw_hit.get("payload")

    if not isinstance(payload, dict):
        return None

    safe_payload = {
        str(key): value
        for key, value in payload.items()
    }

    if safe_payload.get("module") != "quality":
        return None

    if safe_payload.get("allow_answer_reference") is not True:
        return None

    if safe_payload.get("allow_commitment_reference") is not False:
        return None

    content = as_text(safe_payload.get("content"))

    if not content:
        return None

    score = raw_hit.get("score")

    if not isinstance(score, int | float):
        score = raw_hit.get("distance")

    normalized_score = float(score) if isinstance(score, int | float) else None

    metadata = safe_payload.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    return QualityKBHit(
        point_id=as_text(raw_hit.get("id")),
        score=normalized_score,
        chunk_id=as_text(safe_payload.get("chunk_id")),
        content=content,
        summary=as_text(safe_payload.get("summary")),
        doc_id=as_text(safe_payload.get("doc_id")),
        doc_title=as_text(safe_payload.get("doc_title")),
        source_name=as_text(safe_payload.get("source_name")),
        source_uri=as_text(safe_payload.get("source_uri")),
        risk_level=as_text(safe_payload.get("risk_level")),
        sku_scope=as_text_list(safe_payload.get("sku_scope")),
        intent_scope=as_text_list(safe_payload.get("intent_scope")),
        is_verified=bool(safe_payload.get("is_verified")),
        allow_answer_reference=bool(safe_payload.get("allow_answer_reference")),
        allow_commitment_reference=bool(
            safe_payload.get("allow_commitment_reference")
        ),
        metadata={
            str(key): value
            for key, value in metadata.items()
        },
    )


def normalize_raw_hits(
    raw_hits: list[Any],
) -> list[dict[str, Any]]:
    """Normalize raw Qdrant hits."""

    hits: list[dict[str, Any]] = []

    for raw_hit in raw_hits:
        if isinstance(raw_hit, dict):
            hits.append(
                {
                    str(key): value
                    for key, value in raw_hit.items()
                }
            )

    return hits


def get_qdrant_url() -> str:
    """Return Qdrant URL."""

    explicit = os.getenv("QDRANT_URL", "").strip()

    if explicit:
        return explicit.rstrip("/")

    host = os.getenv("QDRANT_HOST", "").strip() or "127.0.0.1"
    port = os.getenv("QDRANT_PORT", "").strip() or "6333"

    return f"http://{host}:{port}".rstrip("/")


def get_quality_collection_name() -> str:
    """Return quality collection name."""

    return (
        os.getenv("QDRANT_COLLECTION_QUALITY", "").strip()
        or DEFAULT_COLLECTION_NAME
    )


def get_embedding_model() -> str:
    """Return embedding model name."""

    return os.getenv("EMBEDDING_MODEL", "").strip() or "BAAI/bge-m3"


def get_quality_top_k() -> int:
    """Return quality top_k."""

    value = os.getenv("QUALITY_KB_TOP_K", "").strip()

    if value.isdigit():
        return max(1, min(int(value), 10))

    return DEFAULT_TOP_K


def as_text(
    value: object,
) -> str:
    """Return stripped text."""

    if value is None:
        return ""

    return str(value).strip()


def as_text_list(
    value: object,
) -> list[str]:
    """Return list of text."""

    if value is None:
        return []

    if isinstance(value, list):
        return [
            as_text(item)
            for item in value
            if as_text(item)
        ]

    if isinstance(value, str):
        if not value.strip():
            return []

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [
                item.strip()
                for item in value.split(";")
                if item.strip()
            ]

        if isinstance(parsed, list):
            return [
                as_text(item)
                for item in parsed
                if as_text(item)
            ]

    return [as_text(value)] if as_text(value) else []