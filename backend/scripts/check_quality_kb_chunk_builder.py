# ruff: noqa: E402,I001
"""Check quality KB chunk builder."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Final[Path] = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag.quality_chunk_builder import (
    QualityKBChunk,
    build_quality_kb_chunks,
    load_quality_qa_records,
)


QUALITY_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "uploads"
    / "qa_pairs"
    / "quality_questions.xlsx"
)

FORBIDDEN_OUTPUT_FRAGMENTS: Final[tuple[str, ...]] = (
    "保证最低价",
    "最低价给你",
    "一定包邮",
    "保证到货",
    "今天一定发",
    "保证不坏",
    "保证不生锈",
    "保证不掉漆",
    "保证耐用",
    "能用几年",
    "一年质保",
    "终身质保",
    "七天无理由",
    "一定能退",
    "一定能换",
    "一定赔",
    "一定补发",
    "质量很好",
    "放心用",
    "完全没问题",
)


def check_quality_kb_chunk_builder() -> bool:
    """Check quality KB chunk builder."""

    print("=" * 80)
    print("checking quality KB chunk builder")
    print(f"quality_file={QUALITY_FILE}")

    if not QUALITY_FILE.exists():
        print("failed: quality_questions.xlsx not found")
        return False

    records = load_quality_qa_records(workbook_path=QUALITY_FILE)
    chunks = build_quality_kb_chunks(
        records=records,
        source_uri=str(QUALITY_FILE),
    )

    errors: list[str] = []
    warnings: list[str] = []

    chunk_ids = [chunk.chunk_id for chunk in chunks]
    content_hashes = [chunk.content_hash for chunk in chunks]

    if len(records) != 50:
        errors.append(f"expected 50 records, got {len(records)}")

    if len(chunks) != len(records):
        errors.append(
            f"chunk count mismatch: records={len(records)}, chunks={len(chunks)}"
        )

    if len(set(chunk_ids)) != len(chunk_ids):
        errors.append("duplicated chunk_id detected")

    if len(set(content_hashes)) != len(content_hashes):
        warnings.append("duplicated content_hash detected")

    for chunk in chunks:
        errors.extend(check_one_chunk(chunk))

    api_key = os.getenv("LLM_API_KEY", "").strip()

    if api_key:
        serialized = json.dumps(
            [chunk.to_dict() for chunk in chunks],
            ensure_ascii=False,
        )

        if api_key in serialized:
            errors.append("LLM_API_KEY leaked into chunk serialization")

    risk_counter = Counter(chunk.risk_level for chunk in chunks)
    subtype_counter = Counter(
        str(chunk.metadata.get("record_metadata", {}).get("intent_subtype", ""))
        for chunk in chunks
    )
    verification_counter = Counter(
        "verified" if chunk.is_verified else "not_verified"
        for chunk in chunks
    )
    commitment_counter = Counter(
        str(chunk.allow_commitment_reference).lower()
        for chunk in chunks
    )

    summary = {
        "record_count": len(records),
        "chunk_count": len(chunks),
        "unique_chunk_id_count": len(set(chunk_ids)),
        "unique_content_hash_count": len(set(content_hashes)),
        "risk_level_distribution": dict(risk_counter),
        "verification_distribution": dict(verification_counter),
        "allow_commitment_reference_distribution": dict(commitment_counter),
        "sample_chunk": chunks[0].to_dict() if chunks else None,
        "warnings": warnings,
        "errors": errors,
    }

    pprint(summary)

    # Keep visible but do not fail if subtype metadata was not nested.
    if subtype_counter:
        print("metadata subtype distribution:")
        pprint(dict(subtype_counter))

    if errors:
        print("quality KB chunk builder check failed")
        return False

    print("quality KB chunk builder check passed")
    return True


def check_one_chunk(
    chunk: QualityKBChunk,
) -> list[str]:
    """Check one chunk."""

    errors: list[str] = []

    if not chunk.chunk_id.startswith("quality_qa_qual"):
        errors.append(f"{chunk.chunk_id}: invalid chunk_id prefix")

    if chunk.module != "quality":
        errors.append(f"{chunk.chunk_id}: module must be quality")

    if chunk.source_type != "qa_pair":
        errors.append(f"{chunk.chunk_id}: source_type must be qa_pair")

    if chunk.source_name != "quality_questions.xlsx":
        errors.append(f"{chunk.chunk_id}: source_name mismatch")

    if not chunk.source_uri:
        errors.append(f"{chunk.chunk_id}: source_uri is empty")

    if not chunk.doc_id.startswith("QUAL"):
        errors.append(f"{chunk.chunk_id}: doc_id must start with QUAL")

    if chunk.chunk_index < 0:
        errors.append(f"{chunk.chunk_id}: chunk_index must be non-negative")

    if "quality" not in chunk.intent_scope:
        errors.append(f"{chunk.chunk_id}: intent_scope missing quality")

    if not chunk.content.strip():
        errors.append(f"{chunk.chunk_id}: content is empty")

    if len(chunk.content_hash) != 64:
        errors.append(f"{chunk.chunk_id}: content_hash must be sha256")

    if not chunk.summary.strip():
        errors.append(f"{chunk.chunk_id}: summary is empty")

    if chunk.language != "zh":
        errors.append(f"{chunk.chunk_id}: language must be zh")

    if chunk.risk_level not in {"low", "medium", "high"}:
        errors.append(f"{chunk.chunk_id}: invalid risk_level={chunk.risk_level}")

    if chunk.allow_commitment_reference is not False:
        errors.append(
            f"{chunk.chunk_id}: allow_commitment_reference must be false"
        )

    if chunk.allow_answer_reference is not True:
        errors.append(f"{chunk.chunk_id}: allow_answer_reference must be true")

    for fragment in FORBIDDEN_OUTPUT_FRAGMENTS:
        if fragment in chunk.content:
            errors.append(
                f"{chunk.chunk_id}: chunk content contains forbidden phrase "
                f"{fragment!r}"
            )

    return errors


def main() -> int:
    """Run quality KB chunk builder check."""

    try:
        passed = check_quality_kb_chunk_builder()
    except Exception as exc:
        print(
            "quality KB chunk builder check crashed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())