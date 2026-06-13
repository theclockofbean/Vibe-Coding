"""Export Price KB retriever from app.agent.rag."""

from __future__ import annotations

from pathlib import Path

INIT_FILE = Path("app/agent/rag/__init__.py")


def main() -> int:
    """Patch rag __init__.py."""

    content = INIT_FILE.read_text(encoding="utf-8")

    import_line = (
        "from app.agent.rag.price_kb_retriever import "
        "PriceKBHit, PriceKBQdrantRetriever\n"
    )

    if import_line not in content:
        content += "\n" + import_line

    if "__all__" in content:
        content = ensure_all_item(content, "PriceKBHit")
        content = ensure_all_item(content, "PriceKBQdrantRetriever")
    else:
        content += (
            "\n__all__ = [\n"
            '    "PriceKBHit",\n'
            '    "PriceKBQdrantRetriever",\n'
            "]\n"
        )

    INIT_FILE.write_text(content, encoding="utf-8")

    print("Price KB retriever exported")
    return 0


def ensure_all_item(
    content: str,
    item: str,
) -> str:
    """Ensure item exists in __all__ list."""

    quoted_item = f'"{item}"'

    if quoted_item in content or f"'{item}'" in content:
        return content

    marker = "__all__ = ["

    if marker not in content:
        return content

    return content.replace(
        marker,
        f'{marker}\n    "{item}",',
        1,
    )


if __name__ == "__main__":
    raise SystemExit(main())