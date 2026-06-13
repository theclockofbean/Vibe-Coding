"""Fix Logistics Qdrant upsert embedding request batching."""

from __future__ import annotations

import re
from pathlib import Path

UPSERT_FILE = Path("scripts/upsert_logistics_kb_chunks_to_qdrant.py")


def main() -> int:
    """Patch embed_texts to batch embedding requests."""

    content = UPSERT_FILE.read_text(encoding="utf-8")

    pattern = re.compile(
        r"def embed_texts\(\n"
        r"[\s\S]*?\n"
        r"def build_qdrant_points\(",
        re.MULTILINE,
    )

    replacement = '''def embed_texts(
    *,
    client: httpx.Client,
    embedding_base_url: str,
    embedding_model: str,
    texts: list[str],
) -> list[list[float]]:
    """Call OpenAI-compatible embedding endpoint in small batches."""

    url = f"{embedding_base_url.rstrip('/')}/v1/embeddings"
    batch_size = get_int_env("EMBEDDING_BATCH_SIZE", 8)

    if batch_size <= 0:
        raise RuntimeError(f"EMBEDDING_BATCH_SIZE must be positive, got {batch_size}")

    embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start : start + batch_size]
        payload = {
            "model": embedding_model,
            "input": batch_texts,
        }

        response = client.post(url, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(
                "embedding request failed: "
                f"status={response.status_code}, "
                f"batch_start={start}, "
                f"batch_size={len(batch_texts)}, "
                f"body={response.text[:1000]}"
            )

        data = response.json()
        raw_items = data.get("data")

        if not isinstance(raw_items, list):
            raise RuntimeError(f"unexpected embedding response: {data}")

        for item in raw_items:
            if not isinstance(item, dict):
                raise RuntimeError(f"unexpected embedding item: {item}")

            embedding = item.get("embedding")

            if not isinstance(embedding, list):
                raise RuntimeError(f"missing embedding vector: {item}")

            embeddings.append([float(value) for value in embedding])

    return embeddings


def build_qdrant_points('''

    new_content, count = pattern.subn(replacement, content, count=1)

    if count != 1:
        raise RuntimeError("embed_texts function block not found or replaced more than once")

    UPSERT_FILE.write_text(new_content, encoding="utf-8")

    print("logistics Qdrant upsert embedding batching fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())