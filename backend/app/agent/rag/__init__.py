"""RAG package exports."""

from app.agent.rag.embedding import (
    DeterministicHashEmbeddingClient,
    EmbeddingClient,
    validate_embedding_vector,
)
from app.agent.rag.evidence_filter import (
    EvidenceFilterResult,
    RAGEvidenceFilter,
    filter_retrieved_chunk_dicts,
)
from app.agent.rag.qdrant_retriever import (
    QdrantRetriever,
    build_default_qdrant_retriever,
)
from app.agent.rag.qdrant_store import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_DISTANCE,
    DEFAULT_QDRANT_URL,
    DEFAULT_QDRANT_VECTOR_SIZE,
    QdrantCollectionConfig,
    QdrantStoreError,
    QdrantVectorStore,
)
from app.agent.rag.retriever import (
    LocalKnowledgeChunkRetriever,
    NullRetriever,
    Retriever,
    ensure_retrieved_chunk_dicts,
)
from app.agent.rag.schemas import (
    DEFAULT_COLLECTION_NAME,
    KnowledgeChunk,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
    sha256_text,
)

__all__ = [
    "SpecKBRetrievalHit",
    "SpecKBQdrantRetrieverConfig",
    "SpecKBQdrantRetriever",
    "PriceKBQdrantRetriever",
    "PriceKBHit",
    "DEFAULT_COLLECTION_NAME",
    "DEFAULT_QDRANT_COLLECTION",
    "DEFAULT_QDRANT_DISTANCE",
    "DEFAULT_QDRANT_URL",
    "DEFAULT_QDRANT_VECTOR_SIZE",
    "DeterministicHashEmbeddingClient",
    "EmbeddingClient",
    "EvidenceFilterResult",
    "KnowledgeChunk",
    "LocalKnowledgeChunkRetriever",
    "NullRetriever",
    "QdrantCollectionConfig",
    "QdrantRetriever",
    "QdrantStoreError",
    "QdrantVectorStore",
    "RAGEvidenceFilter",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievedChunk",
    "Retriever",
    "build_default_qdrant_retriever",
    "ensure_retrieved_chunk_dicts",
    "filter_retrieved_chunk_dicts",
    "sha256_text",
    "validate_embedding_vector",
    "LogisticsKBHit",
    "LogisticsKBQdrantRetriever",
]
from app.agent.rag.logistics_kb_retriever import (
    LogisticsKBHit,
    LogisticsKBQdrantRetriever,
)
from app.agent.rag.price_kb_retriever import PriceKBHit, PriceKBQdrantRetriever

from .quality_kb_retriever import QualityKBHit as QualityKBHit
from .quality_kb_retriever import QualityKBQdrantRetriever as QualityKBQdrantRetriever
from .real_embedding import OpenAICompatibleEmbeddingClient as OpenAICompatibleEmbeddingClient
from .real_embedding import RealEmbeddingClient as RealEmbeddingClient
from .real_embedding import RealEmbeddingConfig as RealEmbeddingConfig
from .real_embedding import RealEmbeddingError as RealEmbeddingError
from .real_embedding import (
    build_real_embedding_client_from_env as build_real_embedding_client_from_env,
)
from .real_embedding import real_embedding_enabled_from_env as real_embedding_enabled_from_env
from .spec_kb_retriever import SpecKBQdrantRetriever as SpecKBQdrantRetriever
from .spec_kb_retriever import SpecKBQdrantRetrieverConfig as SpecKBQdrantRetrieverConfig
from .spec_kb_retriever import SpecKBRetrievalHit as SpecKBRetrievalHit