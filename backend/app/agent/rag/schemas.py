"""RAG schemas.

These schemas define internal contracts for retrieved knowledge chunks.

They do not call an LLM, generate embeddings, call Qdrant, generate answers,
promise prices, promise logistics, promise quality, promise warranty, promise
returns/exchanges, or create business commitments.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Final

DEFAULT_COLLECTION_NAME: Final[str] = "kb_chunks_v1"
DEFAULT_LANGUAGE: Final[str] = "zh"
DEFAULT_VERSION: Final[str] = "v1"

ALLOWED_MODULES: Final[set[str]] = {
    "spec",
    "price",
    "logistics",
    "quality",
    "general",
}

ALLOWED_RISK_LEVELS: Final[set[str]] = {
    "low",
    "medium",
    "high",
}

SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class KnowledgeChunk:
    """Metadata contract for one knowledge chunk."""

    chunk_id: str
    source_type: str
    source_name: str
    doc_id: str
    doc_title: str
    chunk_index: int
    module: str
    content: str

    collection_name: str = DEFAULT_COLLECTION_NAME
    source_uri: str | None = None
    sku_scope: list[str] = field(default_factory=list)
    intent_scope: list[str] = field(default_factory=list)
    content_hash: str = ""
    summary: str | None = None
    language: str = DEFAULT_LANGUAGE
    risk_level: str = "low"
    is_active: bool = True
    is_verified: bool = False
    allow_answer_reference: bool = True
    allow_commitment_reference: bool = False
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    qdrant_point_id: str | None = None
    version: str = DEFAULT_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize chunk contract."""

        _require_non_blank("chunk_id", self.chunk_id)
        _require_non_blank("source_type", self.source_type)
        _require_non_blank("source_name", self.source_name)
        _require_non_blank("doc_id", self.doc_id)
        _require_non_blank("doc_title", self.doc_title)
        _require_non_blank("module", self.module)
        _require_non_blank("content", self.content)

        if self.chunk_index < 0:
            raise ValueError("chunk_index must be >= 0")

        validate_module(self.module)
        validate_risk_level(self.risk_level)

        if self.embedding_dimension is not None and self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")

        content_hash = self.content_hash or sha256_text(self.content)

        if not SHA256_PATTERN.match(content_hash):
            raise ValueError("content_hash must be lowercase sha256 hex")

        object.__setattr__(self, "content_hash", content_hash)

        if self.allow_commitment_reference and not self.is_verified:
            raise ValueError(
                "allow_commitment_reference requires is_verified=True"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "chunk_id": self.chunk_id,
            "collection_name": self.collection_name,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_uri": self.source_uri,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "chunk_index": self.chunk_index,
            "module": self.module,
            "sku_scope": list(self.sku_scope),
            "intent_scope": list(self.intent_scope),
            "content": self.content,
            "content_hash": self.content_hash,
            "summary": self.summary,
            "language": self.language,
            "risk_level": self.risk_level,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "allow_answer_reference": self.allow_answer_reference,
            "allow_commitment_reference": self.allow_commitment_reference,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "qdrant_point_id": self.qdrant_point_id,
            "version": self.version,
            "metadata": dict(self.metadata),
        }

    def to_retrieved_chunk(
        self,
        *,
        score: float,
    ) -> RetrievedChunk:
        """Convert metadata chunk to retrieved chunk."""

        return RetrievedChunk(
            collection=self.collection_name,
            chunk_id=self.chunk_id,
            source_type=self.source_type,
            source_name=self.source_name,
            doc_id=self.doc_id,
            doc_title=self.doc_title,
            chunk_index=self.chunk_index,
            module=self.module,
            content=self.content,
            score=score,
            summary=self.summary,
            risk_level=self.risk_level,
            is_active=self.is_active,
            is_verified=self.is_verified,
            allow_answer_reference=self.allow_answer_reference,
            allow_commitment_reference=self.allow_commitment_reference,
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class RetrievedChunk:
    """One chunk returned by a retriever."""

    collection: str
    chunk_id: str
    source_type: str
    source_name: str
    doc_id: str
    doc_title: str
    chunk_index: int
    module: str
    content: str
    score: float

    summary: str | None = None
    risk_level: str = "low"
    is_active: bool = True
    is_verified: bool = False
    allow_answer_reference: bool = True
    allow_commitment_reference: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate retrieved chunk contract."""

        _require_non_blank("collection", self.collection)
        _require_non_blank("chunk_id", self.chunk_id)
        _require_non_blank("source_type", self.source_type)
        _require_non_blank("source_name", self.source_name)
        _require_non_blank("doc_id", self.doc_id)
        _require_non_blank("doc_title", self.doc_title)
        _require_non_blank("module", self.module)
        _require_non_blank("content", self.content)

        if self.chunk_index < 0:
            raise ValueError("chunk_index must be >= 0")

        if self.score < 0:
            raise ValueError("score must be >= 0")

        validate_module(self.module)
        validate_risk_level(self.risk_level)

        if self.allow_commitment_reference and not self.is_verified:
            raise ValueError(
                "allow_commitment_reference requires is_verified=True"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dict."""

        return {
            "collection": self.collection,
            "chunk_id": self.chunk_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "chunk_index": self.chunk_index,
            "module": self.module,
            "content": self.content,
            "summary": self.summary,
            "score": self.score,
            "risk_level": self.risk_level,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "allow_answer_reference": self.allow_answer_reference,
            "allow_commitment_reference": self.allow_commitment_reference,
            "metadata": dict(self.metadata),
        }

    def to_source_reference(self) -> dict[str, Any]:
        """Return AgentState source reference dict."""

        return {
            "source_type": "rag_chunk",
            "source_name": self.source_name,
            "reference_id": self.chunk_id,
            "collection": self.collection,
            "score": self.score,
            "module": self.module,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
        }


@dataclass(frozen=True)
class RetrievalQuery:
    """Retriever query contract."""

    query: str
    selected_module: str | None = None
    matched_sku: str | None = None
    top_k: int = 5
    language: str = DEFAULT_LANGUAGE
    min_score: float = 0.0

    def __post_init__(self) -> None:
        """Validate retrieval query."""

        _require_non_blank("query", self.query)

        if self.selected_module is not None:
            validate_module(self.selected_module)

        if self.top_k < 1 or self.top_k > 50:
            raise ValueError("top_k must be between 1 and 50")

        if self.min_score < 0 or self.min_score > 1:
            raise ValueError("min_score must be between 0 and 1")

    @property
    def normalized_query(self) -> str:
        """Return normalized query text."""

        return self.query.strip()


@dataclass(frozen=True)
class RetrievalResult:
    """Retriever result contract."""

    chunks: list[RetrievedChunk] = field(default_factory=list)
    rejected_chunks: list[RetrievedChunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_retrieved_chunk_dicts(self) -> list[dict[str, Any]]:
        """Return chunk dicts."""

        return [
            chunk.to_dict()
            for chunk in self.chunks
        ]

    def to_source_references(self) -> list[dict[str, Any]]:
        """Return source references."""

        return [
            chunk.to_source_reference()
            for chunk in self.chunks
        ]


def sha256_text(value: str) -> str:
    """Return lowercase sha256 hex for text."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_module(value: str) -> None:
    """Validate module value."""

    if value not in ALLOWED_MODULES:
        raise ValueError(f"invalid module: {value}")


def validate_risk_level(value: str) -> None:
    """Validate risk level."""

    if value not in ALLOWED_RISK_LEVELS:
        raise ValueError(f"invalid risk_level: {value}")


def _require_non_blank(
    field_name: str,
    value: str,
) -> None:
    """Require non-blank text."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")