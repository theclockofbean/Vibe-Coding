# ruff: noqa: E402,I001
"""Check real embedding client contract with mock transport."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Final

import httpx

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.real_embedding import (
    OpenAICompatibleEmbeddingClient,
    RealEmbeddingConfig,
    RealEmbeddingError,
)


def check_success_contract() -> bool:
    """Check success response contract."""

    print("=" * 80)
    print("checking embedding success contract")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))

        if body["model"] != "mock-bge-m3":
            return httpx.Response(400, json={"error": "bad model"})

        if body["input"] != ["hello", "world"]:
            return httpx.Response(400, json={"error": "bad input"})

        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "index": 0,
                        "embedding": [0.1, 0.2, 0.3, 0.4],
                    },
                    {
                        "object": "embedding",
                        "index": 1,
                        "embedding": [0.5, 0.6, 0.7, 0.8],
                    },
                ],
                "model": "mock-bge-m3",
                "usage": {
                    "prompt_tokens": 2,
                    "total_tokens": 2,
                },
            },
        )

    client = OpenAICompatibleEmbeddingClient(
        config=RealEmbeddingConfig(
            provider="mock",
            base_url="https://embedding.example.com/v1",
            api_key="mock-key",
            model="mock-bge-m3",
            dimension=4,
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    vectors = client.embed_texts(["hello", "world"])

    pprint({"vectors": vectors})

    return (
        len(vectors) == 2
        and len(vectors[0]) == 4
        and vectors[0][0] == 0.1
        and vectors[1][3] == 0.8
    )


def check_error_contract() -> bool:
    """Check error response contract."""

    print("=" * 80)
    print("checking embedding error contract")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    client = OpenAICompatibleEmbeddingClient(
        config=RealEmbeddingConfig(
            provider="mock",
            base_url="https://embedding.example.com/v1",
            api_key="mock-key",
            model="mock-bge-m3",
            dimension=4,
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    try:
        client.embed_texts(["hello"])
    except RealEmbeddingError as exc:
        print(f"caught expected RealEmbeddingError: {exc}")
        return True

    return False


def check_dimension_mismatch() -> bool:
    """Check dimension mismatch."""

    print("=" * 80)
    print("checking embedding dimension mismatch")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [0.1, 0.2],
                    }
                ]
            },
        )

    client = OpenAICompatibleEmbeddingClient(
        config=RealEmbeddingConfig(
            provider="mock",
            base_url="https://embedding.example.com/v1",
            api_key="mock-key",
            model="mock-bge-m3",
            dimension=4,
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    try:
        client.embed_texts(["hello"])
    except RealEmbeddingError as exc:
        print(f"caught expected dimension error: {exc}")
        return "dimension mismatch" in str(exc)

    return False


def check_incomplete_config() -> bool:
    """Check incomplete config."""

    print("=" * 80)
    print("checking embedding incomplete config")

    client = OpenAICompatibleEmbeddingClient(
        config=RealEmbeddingConfig(
            provider="mock",
            base_url="",
            api_key="",
            model="",
            dimension=None,
            max_retries=0,
        ),
    )

    try:
        client.embed_texts(["hello"])
    except RealEmbeddingError as exc:
        print(f"caught expected incomplete config error: {exc}")
        return "incomplete" in str(exc)

    return False


def main() -> int:
    """Run checks."""

    results = [
        check_success_contract(),
        check_error_contract(),
        check_dimension_mismatch(),
        check_incomplete_config(),
    ]

    print("=" * 80)

    if not all(results):
        print("real embedding client contract check failed")
        return 1

    print("real embedding client contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())