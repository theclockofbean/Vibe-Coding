"""Real embedding client for OpenAI-compatible embedding APIs."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


class RealEmbeddingError(RuntimeError):
    """Real embedding client error."""


class RealEmbeddingClient(Protocol):
    """Real embedding client protocol."""

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed a list of texts."""


@dataclass(frozen=True)
class RealEmbeddingConfig:
    """OpenAI-compatible embedding config."""

    provider: str = "local"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    dimension: int | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 2
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> RealEmbeddingConfig:
        """Build config from environment."""

        dimension_text = os.getenv("EMBEDDING_DIMENSION", "").strip()
        dimension = int(dimension_text) if dimension_text.isdigit() else None

        return cls(
            provider=os.getenv("EMBEDDING_PROVIDER", "local").strip() or "local",
            base_url=os.getenv("EMBEDDING_BASE_URL", "").strip(),
            api_key=os.getenv("EMBEDDING_API_KEY", "").strip(),
            model=os.getenv("EMBEDDING_MODEL", "").strip(),
            dimension=dimension,
            timeout_seconds=float(
                os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30").strip() or "30"
            ),
            max_retries=int(
                os.getenv("EMBEDDING_MAX_RETRIES", "2").strip() or "2"
            ),
        )

    @property
    def is_complete(self) -> bool:
        """Return whether config can call real embedding API."""

        return bool(self.base_url and self.model)

    @property
    def embeddings_url(self) -> str:
        """Return embeddings endpoint URL."""

        base = self.base_url.rstrip("/")

        if base.endswith("/embeddings"):
            return base

        if base.endswith("/v1"):
            return f"{base}/embeddings"

        return f"{base}/v1/embeddings"


@dataclass
class OpenAICompatibleEmbeddingClient:
    """OpenAI-compatible embedding client."""

    config: RealEmbeddingConfig
    transport: httpx.BaseTransport | None = None

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed a list of texts."""

        normalized_texts = [text.strip() for text in texts]

        if not normalized_texts:
            return []

        if any(not text for text in normalized_texts):
            raise RealEmbeddingError("embedding input contains empty text")

        if not self.config.is_complete:
            raise RealEmbeddingError("real embedding config is incomplete")

        payload = {
            "model": self.config.model,
            "input": normalized_texts,
        }

        headers = {
            "Content-Type": "application/json",
        }

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        last_error: Exception | None = None

        for attempt_index in range(self.config.max_retries + 1):
            try:
                response_payload = self._post_embeddings(
                    payload=payload,
                    headers=headers,
                )
                vectors = _extract_vectors(response_payload)

                if len(vectors) != len(normalized_texts):
                    raise RealEmbeddingError(
                        "embedding response count does not match input count"
                    )

                self._validate_vectors(vectors)

                return vectors
            except (
                httpx.HTTPError,
                httpx.TimeoutException,
                RealEmbeddingError,
                ValueError,
                KeyError,
                TypeError,
            ) as exc:
                last_error = exc

                if attempt_index >= self.config.max_retries:
                    break

                time.sleep(min(0.2 * (attempt_index + 1), 1.0))

        raise RealEmbeddingError(
            f"embedding request failed: {type(last_error).__name__}: {last_error}"
        )

    def _post_embeddings(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Post embedding request."""

        with httpx.Client(
            timeout=self.config.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = client.post(
                self.config.embeddings_url,
                json=payload,
                headers=headers,
            )

        if response.status_code >= 400:
            raise RealEmbeddingError(
                f"embedding API returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        data = response.json()

        if not isinstance(data, dict):
            raise RealEmbeddingError("embedding API response must be JSON object")

        return {
            str(key): value
            for key, value in data.items()
        }

    def _validate_vectors(
        self,
        vectors: list[list[float]],
    ) -> None:
        """Validate vector dimensions."""

        if not vectors:
            raise RealEmbeddingError("embedding response is empty")

        dimensions = {len(vector) for vector in vectors}

        if len(dimensions) != 1:
            raise RealEmbeddingError(
                f"embedding vectors have inconsistent dimensions: {dimensions}"
            )

        actual_dimension = next(iter(dimensions))

        if actual_dimension <= 0:
            raise RealEmbeddingError("embedding dimension must be positive")

        if self.config.dimension is not None and actual_dimension != self.config.dimension:
            raise RealEmbeddingError(
                "embedding dimension mismatch: "
                f"expected={self.config.dimension}, actual={actual_dimension}"
            )


def build_real_embedding_client_from_env() -> OpenAICompatibleEmbeddingClient:
    """Build real embedding client from env."""

    return OpenAICompatibleEmbeddingClient(
        config=RealEmbeddingConfig.from_env(),
    )


def real_embedding_enabled_from_env() -> bool:
    """Return whether real embedding API is enabled."""

    return os.getenv("EMBEDDING_ENABLE_REAL_API", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _extract_vectors(
    payload: dict[str, Any],
) -> list[list[float]]:
    """Extract vectors from OpenAI-compatible embedding response."""

    data = payload.get("data")

    if not isinstance(data, list):
        raise RealEmbeddingError("embedding response missing data list")

    indexed_items: list[tuple[int, list[float]]] = []

    for fallback_index, item in enumerate(data):
        if not isinstance(item, dict):
            raise RealEmbeddingError("embedding data item must be object")

        embedding = item.get("embedding")

        if not isinstance(embedding, list):
            raise RealEmbeddingError("embedding field must be list")

        vector = [_coerce_float(value) for value in embedding]
        index = item.get("index", fallback_index)

        if not isinstance(index, int):
            index = fallback_index

        indexed_items.append((index, vector))

    indexed_items.sort(key=lambda pair: pair[0])

    return [vector for _, vector in indexed_items]


def _coerce_float(
    value: object,
) -> float:
    """Coerce value to float."""

    if isinstance(value, int | float):
        return float(value)

    if isinstance(value, str):
        return float(value)

    raise RealEmbeddingError(f"invalid embedding value type: {type(value).__name__}")