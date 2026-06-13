# ruff: noqa: E402,I001
"""Check Price KB chunk builder."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.price_chunk_builder import (
    DEFAULT_COLLECTION_NAME,
    PriceKBChunk,
    build_price_kb_chunks_from_excel,
)

PRICE_FILE: Final[Path] = (
    PROJECT_ROOT / "data/uploads/conversations/qa_pairs_raw/price_questions.xlsx"
)
EXPECTED_COUNT: Final[int] = 50


def main() -> int:
    """Run check."""

    print("=" * 80)
    print("checking Price KB chunk builder")

    errors: list[str] = []

    if not PRICE_FILE.exists():
        errors.append(f"missing price file: {PRICE_FILE}")
        pprint({"errors": errors})
        return 1

    chunks = build_price_kb_chunks_from_excel(price_file=PRICE_FILE)

    if len(chunks) != EXPECTED_COUNT:
        errors.append(f"expected {EXPECTED_COUNT} chunks, got {len(chunks)}")

    validate_chunks(chunks=chunks, errors=errors)

    result: dict[str, Any] = {
        "price_file": str(PRICE_FILE),
        "collection_name": DEFAULT_COLLECTION_NAME,
        "chunk_count": len(chunks),
        "first_chunk": preview_chunk(chunks[0]) if chunks else None,
        "last_chunk": preview_chunk(chunks[-1]) if chunks else None,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Price KB chunk builder check failed")
        return 1

    print("Price KB chunk builder check passed")
    return 0


def validate_chunks(
    *,
    chunks: list[PriceKBChunk],
    errors: list[str],
) -> None:
    """Validate chunks."""

    chunk_ids = [chunk.chunk_id for chunk in chunks]
    qa_ids = [chunk.qa_id for chunk in chunks]

    if len(chunk_ids) != len(set(chunk_ids)):
        errors.append("duplicated chunk_id found")

    if qa_ids != [f"PRICE{index:04d}" for index in range(1, EXPECTED_COUNT + 1)]:
        errors.append("qa_id sequence must be PRICE0001-PRICE0050")

    for chunk in chunks:
        if chunk.collection_name != "price_kb_v1":
            errors.append(f"{chunk.qa_id}: collection_name must be price_kb_v1")

        if chunk.module != "price":
            errors.append(f"{chunk.qa_id}: module must be price")

        if chunk.primary_intent != "price":
            errors.append(f"{chunk.qa_id}: primary_intent must be price")

        if not chunk.content.strip():
            errors.append(f"{chunk.qa_id}: content is empty")

        if not chunk.answer_standard.strip():
            errors.append(f"{chunk.qa_id}: answer_standard is empty")

        if chunk.allow_commitment_reference is not False:
            errors.append(f"{chunk.qa_id}: allow_commitment_reference must be false")

        if chunk.allow_answer_reference is not True:
            errors.append(f"{chunk.qa_id}: allow_answer_reference must be true")

        payload = chunk.to_qdrant_payload()

        if payload.get("collection_name") != "price_kb_v1":
            errors.append(f"{chunk.qa_id}: payload collection_name mismatch")

        if payload.get("allow_commitment_reference") is not False:
            errors.append(
                f"{chunk.qa_id}: payload allow_commitment_reference must be false"
            )


def preview_chunk(
    chunk: PriceKBChunk,
) -> dict[str, Any]:
    """Preview chunk."""

    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "doc_title": chunk.doc_title,
        "summary": chunk.summary,
        "source_row_index": chunk.source_row_index,
        "collection_name": chunk.collection_name,
        "module": chunk.module,
        "qa_id": chunk.qa_id,
        "intent_subtype": chunk.intent_subtype,
        "related_sku_ids": chunk.related_sku_ids,
        "required_fields": chunk.required_fields,
        "handoff_required": chunk.handoff_required,
        "risk_flags": chunk.risk_flags,
        "risk_level": chunk.risk_level,
        "allow_answer_reference": chunk.allow_answer_reference,
        "allow_commitment_reference": chunk.allow_commitment_reference,
        "content_preview": chunk.content[:300],
    }


if __name__ == "__main__":
    raise SystemExit(main())