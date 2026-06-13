"""Fix static errors in price_kb_retriever.py."""

from __future__ import annotations

from pathlib import Path

TARGET_FILE = Path("app/agent/rag/price_kb_retriever.py")


def main() -> int:
    """Fix mypy optional rstrip errors."""

    content = TARGET_FILE.read_text(encoding="utf-8")

    old = '''        self.qdrant_url = (
            qdrant_url
            or os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL)
        ).rstrip("/")
        self.embedding_base_url = (
            embedding_base_url
            or os.getenv("EMBEDDING_BASE_URL", DEFAULT_EMBEDDING_BASE_URL)
        ).rstrip("/")
'''

    new = '''        qdrant_url_value = qdrant_url
        if not qdrant_url_value:
            qdrant_url_value = os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL

        embedding_base_url_value = embedding_base_url
        if not embedding_base_url_value:
            embedding_base_url_value = (
                os.getenv("EMBEDDING_BASE_URL") or DEFAULT_EMBEDDING_BASE_URL
            )

        self.qdrant_url = qdrant_url_value.rstrip("/")
        self.embedding_base_url = embedding_base_url_value.rstrip("/")
'''

    if old not in content:
        raise RuntimeError("target optional URL block not found")

    content = content.replace(old, new, 1)
    TARGET_FILE.write_text(content, encoding="utf-8")

    print("price_kb_retriever.py static errors fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())