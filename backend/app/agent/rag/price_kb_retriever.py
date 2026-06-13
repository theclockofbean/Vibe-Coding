"""Qdrant retriever adapter for real Price KB."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Final
from urllib import request

DEFAULT_COLLECTION_NAME: Final[str] = "price_kb_v1"
DEFAULT_QDRANT_URL: Final[str] = "http://127.0.0.1:6333"
DEFAULT_EMBEDDING_BASE_URL: Final[str] = "http://127.0.0.1:8088"
DEFAULT_TOP_K: Final[int] = 5
EXPECTED_DIMENSION: Final[int] = 1024


@dataclass(frozen=True)
class PriceKBHit:
    """Price KB retrieval hit."""

    chunk_id: str
    score: float
    payload: dict[str, Any]

    def to_retrieved_chunk(self) -> dict[str, Any]:
        """Convert hit to workflow retrieved chunk dict."""

        chunk = dict(self.payload)
        chunk["score"] = self.score
        chunk["source"] = "qdrant"
        chunk["collection_name"] = DEFAULT_COLLECTION_NAME
        chunk["module"] = "price"
        chunk["allow_answer_reference"] = True
        chunk["allow_commitment_reference"] = False

        if "chunk_id" not in chunk or not str(chunk["chunk_id"]).strip():
            chunk["chunk_id"] = self.chunk_id

        return chunk


class PriceKBQdrantRetriever:
    """Retriever for real Price KB Qdrant collection."""

    def __init__(
        self,
        *,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        qdrant_url: str | None = None,
        embedding_base_url: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        timeout_seconds: float = 120.0,
    ) -> None:
        """Initialize retriever."""

        self.collection_name = collection_name
        qdrant_url_value = qdrant_url
        if not qdrant_url_value:
            qdrant_url_value = os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL

        embedding_base_url_value = embedding_base_url
        if not embedding_base_url_value:
            embedding_base_url_value = (
                os.getenv("EMBEDDING_BASE_URL") or DEFAULT_EMBEDDING_BASE_URL
            )

        self.qdrant_url = qdrant_url_value.rstrip("/")
        self.embedding_base_url = embedding_base_url_value.rstrip("/")
        self.top_k = top_k
        self.timeout_seconds = timeout_seconds

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve Price KB chunks."""

        cleaned_query = query.strip()

        if not cleaned_query:
            return []

        limit = top_k if top_k is not None else self.top_k
        vector = self._embed_text(cleaned_query)
        hits = self._search(vector=vector, limit=limit)

        return [
            hit.to_retrieved_chunk()
            for hit in hits
        ]

    def _embed_text(
        self,
        text: str,
    ) -> list[float]:
        """Embed one text through local TEI."""

        parsed = self._request_json(
            url=f"{self.embedding_base_url}/embed",
            payload={"inputs": [text]},
            method="POST",
            timeout=self.timeout_seconds,
        )

        if not isinstance(parsed, list) or len(parsed) != 1:
            raise ValueError("embedding response must be a list with one vector")

        vector_raw = parsed[0]

        if not isinstance(vector_raw, list):
            raise ValueError("embedding vector must be a list")

        vector = [
            float(value)
            for value in vector_raw
        ]

        if len(vector) != EXPECTED_DIMENSION:
            raise ValueError(
                f"embedding dimension must be {EXPECTED_DIMENSION}, "
                f"got {len(vector)}"
            )

        return vector

    def _search(
        self,
        *,
        vector: list[float],
        limit: int,
    ) -> list[PriceKBHit]:
        """Search Qdrant."""

        parsed = self._request_json(
            url=(
                f"{self.qdrant_url}/collections/"
                f"{self.collection_name}/points/search"
            ),
            payload={
                "vector": vector,
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
            },
            method="POST",
            timeout=self.timeout_seconds,
        )

        result = parsed.get("result") if isinstance(parsed, dict) else None

        if not isinstance(result, list):
            raise ValueError("Qdrant search result must be list")

        hits: list[PriceKBHit] = []

        for item in result:
            if not isinstance(item, dict):
                continue

            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue

            normalized_payload = {
                str(key): value
                for key, value in payload.items()
            }

            if normalized_payload.get("collection_name") != self.collection_name:
                continue

            if normalized_payload.get("module") != "price":
                continue

            chunk_id = str(normalized_payload.get("chunk_id", "")).strip()

            if not chunk_id:
                continue

            score = float(item.get("score", 0.0))

            hits.append(
                PriceKBHit(
                    chunk_id=chunk_id,
                    score=score,
                    payload=normalized_payload,
                )
            )

        return hits

    def _request_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        method: str,
        timeout: float,
    ) -> Any:
        """Request JSON."""

        data = json.dumps(payload).encode("utf-8")

        http_request = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310
            raw_response = response.read().decode("utf-8")

        return json.loads(raw_response)