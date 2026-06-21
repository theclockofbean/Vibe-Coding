from __future__ import annotations

import inspect
import os
from typing import Any, Iterable, List, Sequence

from app.agent.rag.chunk_schema import DocumentChunk
from app.agent.rag.embedding import (
    DeterministicHashEmbeddingClient,
    validate_embedding_vector,
)


class EmbeddingService:
    """
    RAG Embedding 统一服务。

    职责：
    1. 接收文本或 DocumentChunk
    2. 调用 embedding client
    3. 校验 embedding vector
    4. 返回带 embedding 的 DocumentChunk

    设计原则：
    - 生产/集成链路默认使用真实 embedding
    - deterministic hash embedding 仅作为显式 fallback / 单元测试工具
    - vector_size 必须显式校验，避免假向量或错误维度进入 Qdrant
    """

    def __init__(self, client: Any | None = None, vector_size: int | None = None) -> None:
        self.client = client or DeterministicHashEmbeddingClient()
        self.vector_size = vector_size

    def embed_text(self, text: str) -> List[float]:
        vectors = self.embed_texts([text])

        if not vectors:
            raise ValueError("Embedding client returned empty result")

        return vectors[0]

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        cleaned_texts = [str(text or "").strip() for text in texts]

        if not cleaned_texts:
            return []

        if any(not text for text in cleaned_texts):
            raise ValueError("Embedding input contains empty text")

        vectors = self._call_embedding_client(cleaned_texts)

        if len(vectors) != len(cleaned_texts):
            raise ValueError(
                f"Embedding result count mismatch: expected {len(cleaned_texts)}, got {len(vectors)}"
            )

        validated_vectors: List[List[float]] = []

        for vector in vectors:
            expected_dimension = self.vector_size or len(vector)

            validate_embedding_vector(
                vector,
                expected_dimension=expected_dimension,
            )

            if self.vector_size is not None and len(vector) != self.vector_size:
                raise ValueError(
                    f"Embedding vector size mismatch: expected {self.vector_size}, got {len(vector)}"
                )

            validated_vectors.append([float(value) for value in vector])

        return validated_vectors

    def embed_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        embedded_chunks = self.embed_chunks([chunk])

        if not embedded_chunks:
            raise ValueError("Embedding chunk result is empty")

        return embedded_chunks[0]

    def embed_chunks(self, chunks: Iterable[DocumentChunk]) -> List[DocumentChunk]:
        chunk_list = list(chunks)

        if not chunk_list:
            return []

        texts = [chunk.text for chunk in chunk_list]
        vectors = self.embed_texts(texts)

        embedded_chunks: List[DocumentChunk] = []

        for chunk, vector in zip(chunk_list, vectors):
            embedded_chunks.append(
                chunk.model_copy(
                    update={
                        "embedding": vector,
                    }
                )
            )

        return embedded_chunks

    def _call_embedding_client(self, texts: Sequence[str]) -> List[List[float]]:
        """
        兼容项目中不同 embedding client 的方法命名。

        支持优先级：
        1. embed_texts(texts)
        2. embed_documents(texts)
        3. embed_query(text) 循环
        4. embed(text) 循环
        """

        if hasattr(self.client, "embed_texts"):
            return self._normalize_vectors(self.client.embed_texts(list(texts)))

        if hasattr(self.client, "embed_documents"):
            return self._normalize_vectors(self.client.embed_documents(list(texts)))

        if hasattr(self.client, "embed_query"):
            return self._normalize_vectors(
                [self.client.embed_query(text) for text in texts]
            )

        if hasattr(self.client, "embed"):
            method = self.client.embed
            signature = inspect.signature(method)

            if len(signature.parameters) == 1:
                try:
                    result = method(list(texts))
                    vectors = self._normalize_vectors(result)

                    if len(vectors) == len(texts):
                        return vectors
                except Exception:
                    pass

            return self._normalize_vectors([method(text) for text in texts])

        raise TypeError(
            "Unsupported embedding client. Expected one of: embed_texts, embed_documents, embed_query, embed"
        )

    def _normalize_vectors(self, vectors: Any) -> List[List[float]]:
        if vectors is None:
            return []

        if isinstance(vectors, tuple):
            vectors = list(vectors)

        if not isinstance(vectors, list):
            vectors = list(vectors)

        if not vectors:
            return []

        first = vectors[0]

        if isinstance(first, (int, float)):
            return [[float(value) for value in vectors]]

        return [
            [float(value) for value in vector]
            for vector in vectors
        ]


def _load_env_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv()


def _read_embedding_dimension_from_env() -> int | None:
    value = os.getenv("EMBEDDING_DIMENSION", "").strip()

    if not value:
        return None

    if not value.isdigit():
        raise ValueError(f"EMBEDDING_DIMENSION must be integer, got: {value}")

    return int(value)


def build_deterministic_embedding_service() -> EmbeddingService:
    """
    构建 deterministic embedding service。

    仅用于本地极简测试或单元测试，不作为真实 RAG 默认链路。
    """

    return EmbeddingService(client=DeterministicHashEmbeddingClient())


def build_real_embedding_service_from_env() -> EmbeddingService:
    """
    从环境变量构建真实 embedding service。

    必需配置：
    - EMBEDDING_ENABLE_REAL_API=true
    - EMBEDDING_BASE_URL=http://127.0.0.1:8088
    - EMBEDDING_MODEL=BAAI/bge-m3
    - EMBEDDING_DIMENSION=1024
    """

    _load_env_if_available()

    from app.agent.rag.real_embedding import (
        build_real_embedding_client_from_env,
    )

    vector_size = _read_embedding_dimension_from_env()
    client = build_real_embedding_client_from_env()

    return EmbeddingService(
        client=client,
        vector_size=vector_size,
    )


def build_default_embedding_service() -> EmbeddingService:
    """
    默认 embedding service。

    默认策略：
    1. 如果 EMBEDDING_ENABLE_REAL_API=true，使用真实 bge-m3 / TEI embedding
    2. 否则使用 deterministic embedding 作为显式降级

    注意：
    - 真实 RAG / Qdrant 入库 / 检索验证必须开启真实 embedding
    - deterministic embedding 只用于无模型环境下的结构性测试
    """

    _load_env_if_available()

    try:
        from app.agent.rag.real_embedding import real_embedding_enabled_from_env
    except ImportError:
        return build_deterministic_embedding_service()

    if real_embedding_enabled_from_env():
        return build_real_embedding_service_from_env()

    return build_deterministic_embedding_service()
