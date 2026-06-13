# ruff: noqa: E402,I001
"""Check Logistics KB chunk builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.logistics_chunk_builder import (
    LOGISTICS_COLLECTION_NAME,
    LOGISTICS_MODULE,
    build_logistics_kb_chunks,
    load_logistics_qa_records,
)


LOGISTICS_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "uploads"
    / "conversations"
    / "qa_pairs_raw"
    / "logistics_questions.xlsx"
)

EXPECTED_CHUNK_COUNT: Final[int] = 50


def check_logistics_kb_chunk_builder() -> bool:
    """Check Logistics KB chunk builder output."""

    print("=" * 80)
    print("checking Logistics KB chunk builder")

    errors: list[str] = []
    warnings: list[str] = []

    if not LOGISTICS_FILE.exists():
        errors.append(f"logistics file not found: {LOGISTICS_FILE}")
        pprint({"errors": errors, "warnings": warnings})
        return False

    records = load_logistics_qa_records(LOGISTICS_FILE)
    chunks = build_logistics_kb_chunks(records)

    if len(records) != EXPECTED_CHUNK_COUNT:
        errors.append(
            f"record count must be {EXPECTED_CHUNK_COUNT}, got {len(records)}"
        )

    if len(chunks) != EXPECTED_CHUNK_COUNT:
        errors.append(
            f"chunk count must be {EXPECTED_CHUNK_COUNT}, got {len(chunks)}"
        )

    chunk_ids = [chunk.chunk_id for chunk in chunks]

    if len(set(chunk_ids)) != len(chunk_ids):
        errors.append("chunk_id values must be unique")

    high_risk_without_handoff: list[str] = []

    for chunk in chunks:
        if not chunk.chunk_id.startswith("logistics_qa_logi"):
            errors.append(f"{chunk.qa_id}: invalid chunk_id={chunk.chunk_id}")

        if chunk.module != LOGISTICS_MODULE:
            errors.append(f"{chunk.qa_id}: module must be {LOGISTICS_MODULE}")

        if chunk.source_type != "qa_pair":
            errors.append(f"{chunk.qa_id}: source_type must be qa_pair")

        if chunk.source_name != "logistics_questions.xlsx":
            errors.append(
                f"{chunk.qa_id}: source_name must be logistics_questions.xlsx"
            )

        if chunk.qdrant_collection_name != LOGISTICS_COLLECTION_NAME:
            errors.append(
                f"{chunk.qa_id}: qdrant_collection_name must be "
                f"{LOGISTICS_COLLECTION_NAME}"
            )

        if not chunk.content:
            errors.append(f"{chunk.qa_id}: content is empty")

        if not chunk.question:
            errors.append(f"{chunk.qa_id}: question is empty")

        if not chunk.answer:
            errors.append(f"{chunk.qa_id}: answer is empty")

        if chunk.allow_commitment_reference is not False:
            errors.append(
                f"{chunk.qa_id}: allow_commitment_reference must be false"
            )

        if chunk.risk_level == "high" and not chunk.handoff_required:
            high_risk_without_handoff.append(chunk.qa_id)

    if high_risk_without_handoff:
        warnings.append(
            "high-risk logistics chunks without handoff_required=true: "
            f"{high_risk_without_handoff}"
        )

    risk_level_counts: dict[str, int] = {}

    for chunk in chunks:
        risk_level_counts[chunk.risk_level] = (
            risk_level_counts.get(chunk.risk_level, 0) + 1
        )

    result: dict[str, Any] = {
        "file": str(LOGISTICS_FILE),
        "record_count": len(records),
        "chunk_count": len(chunks),
        "expected_chunk_count": EXPECTED_CHUNK_COUNT,
        "chunk_id_first": chunk_ids[0] if chunk_ids else None,
        "chunk_id_last": chunk_ids[-1] if chunk_ids else None,
        "collection_name": LOGISTICS_COLLECTION_NAME,
        "risk_level_counts": risk_level_counts,
        "sample_chunk": chunk_to_preview(chunks[0]) if chunks else None,
        "errors": errors,
        "warnings": warnings,
    }

    output_file = (
        PROJECT_ROOT
        / "data"
        / "parsed"
        / "logistics"
        / "logistics_kb_chunk_builder_check_result.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pprint(result)

    if errors:
        print("Logistics KB chunk builder check failed")
        return False

    print("Logistics KB chunk builder check passed")
    return True


def chunk_to_preview(
    chunk: object,
) -> dict[str, Any]:
    """Convert chunk to safe preview."""

    if not hasattr(chunk, "chunk_id"):
        return {}

    typed_chunk = chunk

    return {
        "chunk_id": getattr(typed_chunk, "chunk_id"),
        "qa_id": getattr(typed_chunk, "qa_id"),
        "module": getattr(typed_chunk, "module"),
        "source_name": getattr(typed_chunk, "source_name"),
        "qdrant_collection_name": getattr(
            typed_chunk,
            "qdrant_collection_name",
        ),
        "risk_level": getattr(typed_chunk, "risk_level"),
        "handoff_required": getattr(typed_chunk, "handoff_required"),
        "allow_answer_reference": getattr(
            typed_chunk,
            "allow_answer_reference",
        ),
        "allow_commitment_reference": getattr(
            typed_chunk,
            "allow_commitment_reference",
        ),
        "content_preview": str(getattr(typed_chunk, "content"))[:240],
    }


def main() -> int:
    """Run check."""

    passed = check_logistics_kb_chunk_builder()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())