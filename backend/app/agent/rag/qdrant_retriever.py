"""Qdrant retriever implementation.

QdrantRetriever retrieves evidence chunks from Qdrant, normalizes payloads into
RetrievedChunk-compatible dictionaries, and keeps business commitments disabled.

It does not call an LLM, generate answers, promise prices, promise logistics,
promise quality, promise warranty, promise returns/exchanges, or create
business commitments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agent.rag.embedding import (
    EmbeddingClient,
    validate_embedding_vector,
)
from app.agent.rag.qdrant_store import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_QDRANT_VECTOR_SIZE,
    QdrantVectorStore,
)
from app.agent.rag.schemas import (
    RetrievalQuery,
)


@dataclass(frozen=True)
class QdrantRetriever:
    """Retriever backed by Qdrant vector search."""

    embedding_client: EmbeddingClient
    vector_store: QdrantVectorStore
    collection_name: str = DEFAULT_QDRANT_COLLECTION
    embedding_dimension: int = DEFAULT_QDRANT_VECTOR_SIZE
    search_limit: int = 50

    def retrieve(
        self,
        *,
        query: str,
        selected_module: str | None,
        matched_sku: str | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve evidence chunk dictionaries from Qdrant."""

        retrieval_query = RetrievalQuery(
            query=query,
            selected_module=selected_module,
            matched_sku=matched_sku,
            top_k=top_k,
        )

        query_vector = self.embedding_client.embed_query(retrieval_query.query)
        validate_embedding_vector(
            query_vector,
            expected_dimension=self.embedding_dimension,
        )

        points = self.vector_store.search_points(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=max(self.search_limit, top_k),
            with_payload=True,
            with_vector=False,
        )

        chunks: list[dict[str, Any]] = []

        for point in points:
            chunk = _point_to_retrieved_chunk_dict(
                point=point,
                query=retrieval_query.query,
                selected_module=selected_module,
                matched_sku=matched_sku,
            )

            if chunk is None:
                continue

            chunks.append(chunk)

        chunks.sort(
            key=lambda chunk: float(chunk.get("score") or 0.0),
            reverse=True,
        )

        return chunks[:top_k]


def build_default_qdrant_retriever(
    *,
    embedding_client: EmbeddingClient,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    embedding_dimension: int = DEFAULT_QDRANT_VECTOR_SIZE,
) -> QdrantRetriever:
    """Build default Qdrant retriever."""

    return QdrantRetriever(
        embedding_client=embedding_client,
        vector_store=QdrantVectorStore(
            base_url=qdrant_url,
            timeout=5.0,
        ),
        collection_name=collection_name,
        embedding_dimension=embedding_dimension,
    )


def _point_to_retrieved_chunk_dict(
    *,
    point: dict[str, Any],
    query: str,
    selected_module: str | None,
    matched_sku: str | None,
) -> dict[str, Any] | None:
    """Convert Qdrant point to RetrievedChunk-compatible dict."""

    payload = point.get("payload")

    if not isinstance(payload, dict):
        return None

    normalized_payload = {
        str(key): value
        for key, value in payload.items()
    }

    module = _optional_text(normalized_payload.get("module"))

    if not _module_matches(
        module=module,
        selected_module=selected_module,
    ):
        return None

    sku_scope = _as_str_list(normalized_payload.get("sku_scope"))

    if not _sku_scope_matches(
        sku_scope=sku_scope,
        matched_sku=matched_sku,
    ):
        return None

    qdrant_score = _float_value(point.get("score"))
    local_score = _local_relevance_score(
        query=query,
        payload=normalized_payload,
        selected_module=selected_module,
        matched_sku=matched_sku,
    )
    score = max(qdrant_score, local_score, 0.01)

    metadata = _optional_dict(normalized_payload.get("metadata"))
    metadata["qdrant_point_id"] = str(point.get("id") or "")
    metadata["qdrant_score"] = qdrant_score
    metadata["retriever"] = "QdrantRetriever"

    return {
        "chunk_id": _required_text(normalized_payload.get("chunk_id")),
        "collection": _required_text(
            normalized_payload.get("collection_name")
        ),
        "collection_name": _required_text(
            normalized_payload.get("collection_name")
        ),
        "source_type": _required_text(normalized_payload.get("source_type")),
        "source_name": _required_text(normalized_payload.get("source_name")),
        "source_uri": _optional_text(normalized_payload.get("source_uri")),
        "doc_id": _optional_text(normalized_payload.get("doc_id")),
        "doc_title": _optional_text(normalized_payload.get("doc_title")),
        "chunk_index": _int_value(normalized_payload.get("chunk_index")),
        "module": _required_text(normalized_payload.get("module")),
        "sku_scope": sku_scope,
        "intent_scope": _as_str_list(normalized_payload.get("intent_scope")),
        "content": _required_text(normalized_payload.get("content")),
        "summary": _optional_text(normalized_payload.get("summary")),
        "language": _required_text(normalized_payload.get("language")),
        "risk_level": _required_text(normalized_payload.get("risk_level")),
        "is_active": _bool_value(normalized_payload.get("is_active")),
        "is_verified": _bool_value(normalized_payload.get("is_verified")),
        "allow_answer_reference": _bool_value(
            normalized_payload.get("allow_answer_reference")
        ),
        "allow_commitment_reference": _bool_value(
            normalized_payload.get("allow_commitment_reference")
        ),
        "score": score,
        "metadata": metadata,
    }


def _module_matches(
    *,
    module: str | None,
    selected_module: str | None,
) -> bool:
    """Return whether module matches selected module or general."""

    if module is None:
        return False

    if selected_module is None:
        return True

    return module in {selected_module, "general"}


def _sku_scope_matches(
    *,
    sku_scope: list[str],
    matched_sku: str | None,
) -> bool:
    """Return whether SKU scope matches."""

    if not sku_scope:
        return True

    if matched_sku is None:
        return True

    return matched_sku.upper() in {
        sku.upper()
        for sku in sku_scope
    }


def _local_relevance_score(
    *,
    query: str,
    payload: dict[str, Any],
    selected_module: str | None,
    matched_sku: str | None,
) -> float:
    """Return deterministic lexical relevance score for stable local tests."""

    candidate_text = " ".join(
        [
            str(payload.get("chunk_id") or ""),
            str(payload.get("doc_title") or ""),
            str(payload.get("summary") or ""),
            str(payload.get("content") or ""),
            " ".join(_as_str_list(payload.get("intent_scope"))),
        ]
    )

    score = _character_overlap_score(
        query=query,
        candidate_text=candidate_text,
    )

    module = _optional_text(payload.get("module"))

    if selected_module is not None and module == selected_module:
        score += 0.2

    if module == "general":
        score += 0.06

    sku_scope = _as_str_list(payload.get("sku_scope"))

    if matched_sku is not None and matched_sku.upper() in {
        sku.upper()
        for sku in sku_scope
    }:
        score += 0.15

    return min(score, 1.0)


def _character_overlap_score(
    *,
    query: str,
    candidate_text: str,
) -> float:
    """Return simple character overlap score."""

    query_chars = {
        char
        for char in query
        if _is_relevant_char(char)
    }
    candidate_chars = {
        char
        for char in candidate_text
        if _is_relevant_char(char)
    }

    if not query_chars or not candidate_chars:
        return 0.0

    return len(query_chars & candidate_chars) / len(query_chars)


def _is_relevant_char(
    char: str,
) -> bool:
    """Return whether char is relevant for simple lexical score."""

    return char.isalnum() or "\u4e00" <= char <= "\u9fff"


def _required_text(
    value: object,
) -> str:
    """Return required text."""

    text_value = _optional_text(value)

    if text_value is None:
        raise ValueError("required text field is missing")

    return text_value


def _optional_text(
    value: object,
) -> str | None:
    """Return optional text."""

    if value is None:
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    return text_value


def _as_str_list(
    value: object,
) -> list[str]:
    """Return list[str]."""

    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def _optional_dict(
    value: object,
) -> dict[str, Any]:
    """Return dict[str, Any]."""

    if not isinstance(value, dict):
        return {}

    return {
        str(key): item_value
        for key, item_value in value.items()
    }


def _float_value(
    value: object,
) -> float:
    """Return float value."""

    if isinstance(value, int | float):
        return float(value)

    return 0.0


def _int_value(
    value: object,
) -> int:
    """Return int value."""

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.strip().isdigit():
        return int(value)

    return 0


def _bool_value(
    value: object,
) -> bool:
    """Return bool value."""

    return value is True