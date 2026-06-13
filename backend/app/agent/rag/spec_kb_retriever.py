"""Spec KB Qdrant retriever."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, ClassVar, Final, cast
from urllib import request

DEFAULT_COLLECTION_NAME: Final[str] = "spec_kb_v1"
DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_EMBEDDING_BASE_URL: Final[str] = "http://127.0.0.1:8088"
DEFAULT_TOP_K: Final[int] = 5
EXPECTED_DIMENSION: Final[int] = 1024


@dataclass(frozen=True)
class SpecKBRetrievalHit:
    """Spec KB retrieval hit."""

    score: float
    chunk_id: str
    content: str
    payload: dict[str, Any]

    def to_context(self) -> dict[str, Any]:
        """Return normalized context item."""

        return {
            "score": self.score,
            "chunk_id": self.chunk_id,
            "content": self.content,
            "payload": self.payload,
            "collection_name": self.payload.get("collection_name"),
            "module": self.payload.get("module"),
            "qa_id": self.payload.get("qa_id"),
            "intent_subtype": self.payload.get("intent_subtype"),
            "question_normalized": self.payload.get("question_normalized"),
            "answer_standard": self.payload.get("answer_standard"),
            "allow_answer_reference": self.payload.get("allow_answer_reference"),
            "allow_commitment_reference": self.payload.get(
                "allow_commitment_reference"
            ),
        }


@dataclass(frozen=True)
class SpecKBQdrantRetrieverConfig:
    """Spec KB Qdrant retriever config."""

    collection_name: str = DEFAULT_COLLECTION_NAME
    qdrant_url: str = DEFAULT_QDRANT_URL
    embedding_base_url: str = DEFAULT_EMBEDDING_BASE_URL
    embedding_timeout_seconds: float = 240.0
    top_k: int = DEFAULT_TOP_K

    default_top_k: ClassVar[int] = DEFAULT_TOP_K

    @classmethod
    def from_env(cls) -> SpecKBQdrantRetrieverConfig:
        """Build config from env."""

        qdrant_url_value = os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL
        embedding_base_url_value = (
            os.getenv("EMBEDDING_BASE_URL") or DEFAULT_EMBEDDING_BASE_URL
        )
        top_k_value = os.getenv("SPEC_KB_TOP_K") or str(DEFAULT_TOP_K)
        timeout_value = os.getenv("EMBEDDING_TIMEOUT_SECONDS") or "240"

        return cls(
            collection_name=os.getenv("SPEC_KB_COLLECTION_NAME")
            or DEFAULT_COLLECTION_NAME,
            qdrant_url=qdrant_url_value.rstrip("/"),
            embedding_base_url=embedding_base_url_value.rstrip("/"),
            embedding_timeout_seconds=float(timeout_value),
            top_k=max(1, int(top_k_value)),
        )


class SpecKBQdrantRetriever:
    """Retrieve Spec KB chunks from Qdrant."""

    def __init__(
        self,
        config: SpecKBQdrantRetrieverConfig | None = None,
    ) -> None:
        """Initialize retriever."""

        self.config = config or SpecKBQdrantRetrieverConfig.from_env()

    def retrieve(
        self,
        *,
        query: str,
        top_k: int | None = None,
    ) -> list[SpecKBRetrievalHit]:
        """Retrieve Spec KB hits."""

        normalized_query = query.strip()

        if not normalized_query:
            return []

        limit = top_k if top_k is not None else self.config.top_k
        vector = self._embed_one(text=normalized_query)

        if len(vector) != EXPECTED_DIMENSION:
            raise ValueError(
                f"embedding dimension must be {EXPECTED_DIMENSION}, "
                f"got {len(vector)}"
            )

        raw_hits = self._search_qdrant(vector=vector, limit=limit)

        return [
            self._build_hit(raw_hit=raw_hit)
            for raw_hit in raw_hits
        ]

    def retrieve_contexts(
        self,
        *,
        query: str,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve normalized context dictionaries."""

        return [
            hit.to_context()
            for hit in self.retrieve(query=query, top_k=top_k)
        ]

    def _embed_one(
        self,
        *,
        text: str,
    ) -> list[float]:
        """Embed one text."""

        endpoint = f"{self.config.embedding_base_url}/embed"

        response = post_json(
            endpoint=endpoint,
            payload={"inputs": [text]},
            timeout=self.config.embedding_timeout_seconds,
        )

        if not isinstance(response, list) or not response:
            raise ValueError("embedding response must be a non-empty list")

        vector = response[0]

        if not isinstance(vector, list):
            raise ValueError("embedding vector must be a list")

        return [float(value) for value in vector]

    def _search_qdrant(
        self,
        *,
        vector: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search Qdrant collection."""

        endpoint = (
            f"{self.config.qdrant_url}"
            f"/collections/{self.config.collection_name}/points/search"
        )

        response = post_json(
            endpoint=endpoint,
            payload={
                "vector": vector,
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
            },
            timeout=120,
        )

        if not isinstance(response, dict):
            raise ValueError("Qdrant response must be a JSON object")

        hits = response.get("result", [])

        if not isinstance(hits, list):
            raise ValueError("Qdrant search result must be a list")

        return [
            cast(dict[str, Any], hit)
            for hit in hits
            if isinstance(hit, dict)
        ]

    def _build_hit(
        self,
        *,
        raw_hit: dict[str, Any],
    ) -> SpecKBRetrievalHit:
        """Build typed retrieval hit."""

        payload = cast(dict[str, Any], raw_hit.get("payload", {}))

        if payload.get("collection_name") != self.config.collection_name:
            raise ValueError(
                "Spec KB hit collection mismatch: "
                f"{payload.get('collection_name')}"
            )

        if payload.get("module") != "spec":
            raise ValueError(f"Spec KB hit module mismatch: {payload.get('module')}")

        chunk_id = str(payload.get("chunk_id", ""))

        if not chunk_id.startswith("spec_qa_spec"):
            raise ValueError(f"unexpected Spec KB chunk_id: {chunk_id}")

        content = str(payload.get("content", "")).strip()

        if not content:
            raise ValueError(f"{chunk_id}: empty content")

        if not str(payload.get("answer_standard", "")).strip():
            raise ValueError(f"{chunk_id}: empty answer_standard")

        score = float(raw_hit.get("score", 0.0))

        return SpecKBRetrievalHit(
            score=score,
            chunk_id=chunk_id,
            content=content,
            payload=payload,
        )


def post_json(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout: float,
) -> Any:
    """Post JSON and parse response."""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310
        raw_response = response.read().decode("utf-8")

    if not raw_response.strip():
        return {}

    return json.loads(raw_response)