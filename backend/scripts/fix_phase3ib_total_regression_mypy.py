"""Fix mypy issues in Phase 3-I-B total regression files."""

from __future__ import annotations

from pathlib import Path

QDRANT_UPSERT_FILE = Path("scripts/upsert_quality_kb_chunks_to_qdrant.py")
ADAPTER_CHECK_FILE = Path("scripts/check_quality_kb_retriever_adapter.py")


def fix_qdrant_upsert_expected_dimension() -> None:
    """Add assert for expected_dimension after runtime validation."""

    content = QDRANT_UPSERT_FILE.read_text(encoding="utf-8")

    old = '''    if errors:
        pprint(result)
        return False

    try:
        verify_qdrant_collection(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            expected_dimension=expected_dimension,
        )
'''

    new = '''    if errors:
        pprint(result)
        return False

    assert expected_dimension is not None

    try:
        verify_qdrant_collection(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            expected_dimension=expected_dimension,
        )
'''

    if old not in content:
        raise RuntimeError(
            "target block not found in upsert_quality_kb_chunks_to_qdrant.py"
        )

    content = content.replace(old, new, 1)
    QDRANT_UPSERT_FILE.write_text(content, encoding="utf-8")


def fix_adapter_query_errors_type() -> None:
    """Make query_errors explicitly typed before query_result dict."""

    content = ADAPTER_CHECK_FILE.read_text(encoding="utf-8")

    old = '''        query_result = {
            "query": query,
            "hit_count": len(hits),
            "payload_count": len(payloads),
            "top_hit": safe_hit_preview(hits[0]) if hits else None,
            "top_payload": safe_payload_preview(payloads[0]) if payloads else None,
            "errors": [],
        }

        query_errors: list[str] = query_result["errors"]
'''

    new = '''        query_errors: list[str] = []

        query_result: dict[str, Any] = {
            "query": query,
            "hit_count": len(hits),
            "payload_count": len(payloads),
            "top_hit": safe_hit_preview(hits[0]) if hits else None,
            "top_payload": safe_payload_preview(payloads[0]) if payloads else None,
            "errors": query_errors,
        }
'''

    if old not in content:
        raise RuntimeError(
            "target block not found in check_quality_kb_retriever_adapter.py"
        )

    content = content.replace(old, new, 1)
    ADAPTER_CHECK_FILE.write_text(content, encoding="utf-8")


def main() -> int:
    """Run fixes."""

    fix_qdrant_upsert_expected_dimension()
    fix_adapter_query_errors_type()

    print("Phase 3-I-B total regression mypy fixes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())