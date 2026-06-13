"""Embedding client contracts.

Phase 3-E v0.1 provides only protocols and deterministic test embedding.

It does not call external embedding APIs, call an LLM, generate answers, promise
prices, promise logistics, promise quality, or create business commitments.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class EmbeddingClient(Protocol):
    """Embedding client protocol."""

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Embed query text."""


@dataclass(frozen=True)
class DeterministicHashEmbeddingClient:
    """Deterministic embedding client for local contract tests.

    This is not a semantic embedding model. It only provides stable vectors for
    tests and interface validation.
    """

    dimension: int = 8

    def __post_init__(self) -> None:
        """Validate embedding dimension."""

        if self.dimension <= 0:
            raise ValueError("dimension must be positive")

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Return deterministic pseudo-embedding vector."""

        normalized_text = text.strip()

        if not normalized_text:
            raise ValueError("text must not be blank")

        seed = hashlib.sha256(normalized_text.encode("utf-8")).digest()

        return [
            _hash_to_float(
                seed=seed,
                index=index,
            )
            for index in range(self.dimension)
        ]


def validate_embedding_vector(
    vector: list[float],
    *,
    expected_dimension: int,
) -> None:
    """Validate embedding vector shape."""

    if expected_dimension <= 0:
        raise ValueError("expected_dimension must be positive")

    if len(vector) != expected_dimension:
        raise ValueError(
            "embedding vector dimension mismatch: "
            f"expected={expected_dimension}, actual={len(vector)}"
        )

    for item in vector:
        if not isinstance(item, float):
            raise TypeError("embedding vector items must be float")


def _hash_to_float(
    *,
    seed: bytes,
    index: int,
) -> float:
    """Convert hash bytes and index to stable float in [-1, 1]."""

    digest = hashlib.sha256(
        seed + index.to_bytes(4, byteorder="big", signed=False)
    ).digest()

    integer_value = int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=False,
    )

    max_uint64 = float(2**64 - 1)

    return (float(integer_value) / max_uint64) * 2.0 - 1.0