"""Qdrant retriever for real Logistics KB."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Final

import httpx

from app.agent.rag.real_embedding import (
    RealEmbeddingClient,
    build_real_embedding_client_from_env,
)

DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME: Final[str] = "logistics_kb_v1"
DEFAULT_TOP_K: Final[int] = 5


@dataclass(frozen=True)
class LogisticsKBHit:
    """One Logistics KB retrieval hit."""

    point_id: str
    score: float
    payload: dict[str, Any]

    def to_retrieved_chunk(self) -> dict[str, Any]:
        """Convert Qdrant hit to workflow-compatible retrieved chunk."""

        payload = dict(self.payload)

        return {
            "chunk_id": payload.get("chunk_id"),
            "doc_id": payload.get("doc_id"),
            "doc_title": payload.get("doc_title"),
            "summary": payload.get("summary"),
            "content": payload.get("content"),
            "score": self.score,
            "source": "qdrant",
            "source_type": payload.get("source_type") or "qa_pair",
            "source_name": payload.get("source_name") or "logistics_questions.xlsx",
            "module": "logistics",
            "collection_name": payload.get("collection_name") or "logistics_kb_v1",
            "qdrant_point_id": self.point_id,
            "risk_level": payload.get("risk_level"),
            "risk_flags": payload.get("risk_flags"),
            "related_sku_ids": payload.get("related_sku_ids"),
            "sku_scope": payload.get("sku_scope"),
            "intent_scope": payload.get("intent_scope"),
            "verification_status": payload.get("verification_status"),
            "is_verified": payload.get("is_verified"),
            "is_active": payload.get("is_active"),
            "handoff_required": payload.get("handoff_required"),
            "allow_answer_reference": payload.get("allow_answer_reference"),
            "allow_commitment_reference": payload.get("allow_commitment_reference"),
            "metadata": (
                payload.get("metadata")
                if isinstance(payload.get("metadata"), dict)
                else {}
            ),
        }


class LogisticsKBQdrantRetriever:
    """Qdrant retriever for logistics_kb_v1."""

    def __init__(
        self,
        *,
        qdrant_url: str,
        collection_name: str,
        embedding_client: RealEmbeddingClient,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        """Initialize retriever."""

        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection_name = collection_name
        self._embedding_client = embedding_client
        self._top_k = top_k

    @classmethod
    def from_env(cls) -> LogisticsKBQdrantRetriever:
        """Build retriever from env."""

        qdrant_url = get_qdrant_url()
        collection_name = os.getenv(
            "QDRANT_COLLECTION_LOGISTICS",
            DEFAULT_COLLECTION_NAME,
        ).strip() or DEFAULT_COLLECTION_NAME
        top_k = get_int_env("LOGISTICS_KB_TOP_K", DEFAULT_TOP_K)

        return cls(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            embedding_client=build_real_embedding_client_from_env(),
            top_k=top_k,
        )

    @property
    def collection_name(self) -> str:
        """Return collection name."""

        return self._collection_name

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[LogisticsKBHit]:
        """Retrieve Logistics KB hits."""

        cleaned_query = query.strip()

        if not cleaned_query:
            raise ValueError("empty query")

        query_vectors = self._embedding_client.embed_texts([cleaned_query])

        if not query_vectors:
            raise RuntimeError("embedding client returned empty vector list")

        query_vector = query_vectors[0]
        limit = top_k if top_k is not None else self._top_k

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._qdrant_url}/collections/{self._collection_name}/points/search",
                json={
                    "vector": query_vector,
                    "limit": limit,
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
                },
            )
            response.raise_for_status()
            payload = response.json()

        raw_hits = payload.get("result")

        if not isinstance(raw_hits, list):
            raise RuntimeError(f"unexpected Qdrant search response: {payload}")

        hits: list[LogisticsKBHit] = []

        for item in raw_hits:
            if not isinstance(item, dict):
                continue

            item_payload = item.get("payload")

            if not isinstance(item_payload, dict):
                continue

            hits.append(
                LogisticsKBHit(
                    point_id=str(item.get("id") or ""),
                    score=float(item.get("score") or 0.0),
                    payload=item_payload,
                )
            )

        return hits

    def retrieve_chunks(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve workflow-compatible chunk dictionaries."""

        return [
            hit.to_retrieved_chunk()
            for hit in self.retrieve(query, top_k=top_k)
        ]


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