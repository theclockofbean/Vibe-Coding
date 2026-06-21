from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Iterable, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.agent.rag.chunk_schema import DocumentChunk
from app.agent.rag.qdrant_store import (
    DEFAULT_QDRANT_DISTANCE,
    DEFAULT_QDRANT_URL,
)


DEFAULT_CHUNK_COLLECTION = os.getenv("RAG_CHUNK_COLLECTION", "rag_chunks_v1")


def _to_qdrant_distance(distance: str | Distance) -> Distance:
    if isinstance(distance, Distance):
        return distance

    normalized = str(distance or "").strip().lower()

    if normalized == "cosine":
        return Distance.COSINE

    if normalized in {"dot", "dot_product"}:
        return Distance.DOT

    if normalized in {"euclid", "euclidean", "l2"}:
        return Distance.EUCLID

    raise ValueError(f"Unsupported Qdrant distance: {distance}")


def _to_qdrant_point_id(chunk_id: str) -> str:
    """
    Qdrant point id 推荐使用 uint64 或 UUID。

    项目内 chunk_id 使用 sha256，更适合业务追踪；
    因此这里派生稳定 UUID 作为 Qdrant point id，
    原始 chunk_id 保留在 payload 中。
    """
    normalized = str(chunk_id).replace("-", "").strip()

    if len(normalized) >= 32:
        return str(uuid.UUID(hex=normalized[:32]))

    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(chunk_id)))


def _build_domain_filter(domain: Optional[str]) -> Optional[Filter]:
    if not domain:
        return None

    return Filter(
        must=[
            FieldCondition(
                key="domain",
                match=MatchValue(value=domain),
            )
        ]
    )


class ChunkVectorStore:
    """
    DocumentChunk 专用 Qdrant 适配层。

    职责：
    1. 将 DocumentChunk 转为 Qdrant PointStruct
    2. 创建 / 确保 collection
    3. 批量 upsert chunk
    4. 按 query vector 检索 chunk

    兼容：
    - 旧版 qdrant-client: search()
    - 新版 qdrant-client: query_points()
    """

    def __init__(
        self,
        *,
        url: str = DEFAULT_QDRANT_URL,
        api_key: Optional[str] = None,
        collection_name: str = DEFAULT_CHUNK_COLLECTION,
        distance: str | Distance = DEFAULT_QDRANT_DISTANCE,
        client: Optional[QdrantClient] = None,
    ) -> None:
        self.collection_name = collection_name
        self.distance = _to_qdrant_distance(distance)
        self.client = client or QdrantClient(
            url=url,
            api_key=api_key or os.getenv("QDRANT_API_KEY") or None,
        )

    def ensure_collection(self, *, vector_size: int, recreate: bool = False) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be greater than 0")

        existing_collections = {
            collection.name
            for collection in self.client.get_collections().collections
        }

        if self.collection_name in existing_collections:
            if not recreate:
                return

            self.client.delete_collection(collection_name=self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=self.distance,
            ),
        )

    def chunk_to_point(self, chunk: DocumentChunk) -> PointStruct:
        if not chunk.embedding:
            raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

        payload = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "domain": chunk.domain,
            "text": chunk.text,
            "source": chunk.source,
            "source_type": chunk.source_type,
            "metadata": chunk.metadata,
        }

        return PointStruct(
            id=_to_qdrant_point_id(chunk.chunk_id),
            vector=chunk.embedding,
            payload=payload,
        )

    def upsert_chunks(
        self,
        chunks: Iterable[DocumentChunk],
        *,
        batch_size: int = 64,
        ensure_collection: bool = True,
    ) -> int:
        chunk_list = list(chunks)

        if not chunk_list:
            return 0

        first_embedding = chunk_list[0].embedding

        if not first_embedding:
            raise ValueError("First chunk has no embedding; call EmbeddingService before upsert")

        vector_size = len(first_embedding)

        if ensure_collection:
            self.ensure_collection(vector_size=vector_size)

        total = 0

        for start in range(0, len(chunk_list), batch_size):
            batch = chunk_list[start : start + batch_size]
            points = [self.chunk_to_point(chunk) for chunk in batch]

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            total += len(points)

        return total

    def search(
        self,
        query_vector: List[float],
        *,
        limit: int = 5,
        domain: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Any]:

        if not query_vector:
            raise ValueError("query_vector must not be empty")

        query_filter = _build_domain_filter(domain)

        try:
            if hasattr(self.client, "search"):
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=("vector", query_vector),
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False,
                )
                return results or []

            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False,
                )

                if hasattr(response, "points"):
                    return list(response.points or [])

                return list(response or [])

            raise AttributeError("QdrantClient supports neither search() nor query_points()")

        except Exception as e:
            print(f"[QDRANT SEARCH ERROR] {e}")
            return []

    def search_as_dicts(
        self,
        query_vector: List[float],
        *,
        limit: int = 5,
        domain: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:

        results = self.search(
            query_vector=query_vector,
            limit=limit,
            domain=domain,
            score_threshold=score_threshold,
        )

        # ❗关键修复1：防 None
        results = results or []

        items: List[Dict[str, Any]] = []

        for item in results:
            payload = item.payload if hasattr(item, "payload") else {}

            text = (
                payload.get("answer_standard")
                or payload.get("question_normalized")
                or payload.get("content")
                or payload.get("text")
                or ""
            )

            items.append({
                "chunk_id": item.id,
                "document_id": payload.get("document_id"),
                "domain": payload.get("domain"),
                "text": text,
                "source": payload.get("source"),
                "source_type": payload.get("source_type"),
                "score": item.score,
            })

        return items


def build_default_chunk_vector_store() -> ChunkVectorStore:
    return ChunkVectorStore(
        url=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        collection_name=os.getenv("RAG_CHUNK_COLLECTION", DEFAULT_CHUNK_COLLECTION),
        distance=os.getenv("QDRANT_DISTANCE", DEFAULT_QDRANT_DISTANCE),
    )
