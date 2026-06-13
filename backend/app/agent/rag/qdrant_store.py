"""Qdrant vector store wrapper.

This module wraps Qdrant REST APIs for collection management, point upsert,
point retrieve, and vector search.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"
DEFAULT_QDRANT_COLLECTION = "kb_chunks_v1"
DEFAULT_QDRANT_VECTOR_SIZE = 8
DEFAULT_QDRANT_DISTANCE = "Cosine"


class QdrantStoreError(RuntimeError):
    """Qdrant store error."""


@dataclass(frozen=True)
class QdrantCollectionConfig:
    """Qdrant collection vector config."""

    collection_name: str
    vector_size: int
    distance: str
    status: str | None = None
    points_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "collection_name": self.collection_name,
            "vector_size": self.vector_size,
            "distance": self.distance,
            "status": self.status,
            "points_count": self.points_count,
        }


@dataclass(frozen=True)
class QdrantVectorStore:
    """Minimal Qdrant REST wrapper."""

    base_url: str = DEFAULT_QDRANT_URL
    timeout: float = 5.0

    def list_collections(self) -> list[str]:
        """Return collection names."""

        payload = self._request(
            method="GET",
            path="/collections",
        )

        result = _dict_value(payload.get("result"))
        collections = result.get("collections")

        if not isinstance(collections, list):
            return []

        collection_names: list[str] = []

        for item in collections:
            if isinstance(item, dict):
                name = item.get("name")

                if isinstance(name, str):
                    collection_names.append(name)

        return collection_names

    def collection_exists(
        self,
        collection_name: str,
    ) -> bool:
        """Return whether collection exists."""

        _require_non_blank("collection_name", collection_name)

        return collection_name in self.list_collections()

    def ensure_collection(
        self,
        *,
        collection_name: str,
        vector_size: int,
        distance: str = DEFAULT_QDRANT_DISTANCE,
    ) -> QdrantCollectionConfig:
        """Create collection if missing and return config."""

        _require_non_blank("collection_name", collection_name)

        if vector_size <= 0:
            raise ValueError("vector_size must be positive")

        if self.collection_exists(collection_name):
            return self.get_collection_config(collection_name)

        self._request(
            method="PUT",
            path=f"/collections/{collection_name}",
            payload={
                "vectors": {
                    "size": vector_size,
                    "distance": distance,
                },
            },
        )

        return self.get_collection_config(collection_name)

    def get_collection_config(
        self,
        collection_name: str,
    ) -> QdrantCollectionConfig:
        """Return collection vector config."""

        _require_non_blank("collection_name", collection_name)

        payload = self._request(
            method="GET",
            path=f"/collections/{collection_name}",
        )

        result = _dict_value(payload.get("result"))
        config = _dict_value(result.get("config"))
        params = _dict_value(config.get("params"))
        vectors = params.get("vectors")

        vector_size: int | None = None
        distance: str | None = None

        if isinstance(vectors, dict):
            size_value = vectors.get("size")
            distance_value = vectors.get("distance")

            if isinstance(size_value, int):
                vector_size = size_value

            if isinstance(distance_value, str):
                distance = distance_value

        if vector_size is None or distance is None:
            raise QdrantStoreError(
                f"unable to parse vector config for collection: {collection_name}"
            )

        status_value = result.get("status")
        points_count_value = result.get("points_count")

        return QdrantCollectionConfig(
            collection_name=collection_name,
            vector_size=vector_size,
            distance=distance,
            status=status_value if isinstance(status_value, str) else None,
            points_count=(
                points_count_value if isinstance(points_count_value, int) else None
            ),
        )

    def assert_collection_config(
        self,
        *,
        collection_name: str,
        expected_vector_size: int,
        expected_distance: str = DEFAULT_QDRANT_DISTANCE,
    ) -> QdrantCollectionConfig:
        """Validate collection config."""

        config = self.get_collection_config(collection_name)

        if config.vector_size != expected_vector_size:
            raise QdrantStoreError(
                "Qdrant vector size mismatch: "
                f"expected={expected_vector_size}, actual={config.vector_size}"
            )

        if config.distance.lower() != expected_distance.lower():
            raise QdrantStoreError(
                "Qdrant distance mismatch: "
                f"expected={expected_distance}, actual={config.distance}"
            )

        return config

    def upsert_point(
        self,
        *,
        collection_name: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Upsert one point into Qdrant collection."""

        _require_non_blank("collection_name", collection_name)
        _require_non_blank("point_id", point_id)

        if not vector:
            raise ValueError("vector must not be empty")

        self._request(
            method="PUT",
            path=f"/collections/{collection_name}/points?wait=true",
            payload={
                "points": [
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": payload,
                    }
                ],
            },
        )

    def get_points(
        self,
        *,
        collection_name: str,
        point_ids: list[str],
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve points by point IDs."""

        _require_non_blank("collection_name", collection_name)

        if not point_ids:
            return []

        payload = self._request(
            method="POST",
            path=f"/collections/{collection_name}/points",
            payload={
                "ids": point_ids,
                "with_payload": with_payload,
                "with_vector": with_vector,
            },
        )

        result = payload.get("result")

        if not isinstance(result, list):
            return []

        return [
            _dict_value(item)
            for item in result
            if isinstance(item, dict)
        ]

    def search_points(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> list[dict[str, Any]]:
        """Search points by query vector."""

        _require_non_blank("collection_name", collection_name)

        if not query_vector:
            raise ValueError("query_vector must not be empty")

        if limit <= 0:
            raise ValueError("limit must be positive")

        payload = self._request(
            method="POST",
            path=f"/collections/{collection_name}/points/search",
            payload={
                "vector": query_vector,
                "limit": limit,
                "with_payload": with_payload,
                "with_vector": with_vector,
                "filter": {
                    "must": [
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
                        {
                            "key": "language",
                            "match": {
                                "value": "zh",
                            },
                        },
                    ],
                },
            },
        )

        result = payload.get("result")

        if not isinstance(result, list):
            return []

        return [
            _dict_value(item)
            for item in result
            if isinstance(item, dict)
        ]

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute Qdrant REST request."""

        url = self.base_url.rstrip("/") + path
        data: bytes | None = None
        headers = {
            "Content-Type": "application/json",
        }

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = Request(
            url=url,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise QdrantStoreError(
                f"Qdrant HTTP error {exc.code} for {method} {path}: {body}"
            ) from exc
        except URLError as exc:
            raise QdrantStoreError(
                f"Qdrant connection error for {method} {path}: {exc}"
            ) from exc
        except HTTPException as exc:
            raise QdrantStoreError(
                f"Qdrant HTTP protocol error for {method} {path}: {exc}"
            ) from exc

        if not raw_body:
            return {}

        decoded = json.loads(raw_body)

        if not isinstance(decoded, dict):
            raise QdrantStoreError("Qdrant response is not a JSON object")

        status = decoded.get("status")

        if isinstance(status, str) and status.lower() == "error":
            raise QdrantStoreError(f"Qdrant returned error: {decoded}")

        return {
            str(key): value
            for key, value in decoded.items()
        }


def _dict_value(
    value: object,
) -> dict[str, Any]:
    """Return dict value."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _require_non_blank(
    field_name: str,
    value: str,
) -> None:
    """Require non-blank string."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")