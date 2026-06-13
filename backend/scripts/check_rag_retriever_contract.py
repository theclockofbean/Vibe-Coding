# ruff: noqa: E402,I001
"""Check RAG retriever contract.

This script verifies RAG schemas, EmbeddingClient protocol implementation, and
NullRetriever behavior.

It does not call Qdrant, call an LLM, generate answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import (
    DEFAULT_COLLECTION_NAME,
    DeterministicHashEmbeddingClient,
    KnowledgeChunk,
    NullRetriever,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
    ensure_retrieved_chunk_dicts,
    validate_embedding_vector,
)
from app.agent.rag.schemas import sha256_text


FORBIDDEN_COMMITMENT_FRAGMENTS: Final[tuple[str, ...]] = (
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


def check_knowledge_chunk_schema() -> bool:
    """Check KnowledgeChunk contract."""

    print("=" * 80)
    print("checking KnowledgeChunk schema")

    content = "铝合金 6061 是常见轻量化材料；具体质量承诺必须以正式规则或人工确认为准。"

    chunk = KnowledgeChunk(
        chunk_id="contract_quality_chunk_001",
        source_type="manual_doc",
        source_name="rag_contract_check",
        doc_id="quality_boundary_doc",
        doc_title="质量边界说明",
        chunk_index=0,
        module="quality",
        content=content,
        sku_scope=["SKU001"],
        intent_scope=["material_explanation"],
        summary="材料说明，不作为质量承诺。",
        risk_level="medium",
        is_verified=True,
        allow_answer_reference=True,
    )

    chunk_dict = chunk.to_dict()
    retrieved_chunk = chunk.to_retrieved_chunk(score=0.82)
    retrieved_dict = retrieved_chunk.to_dict()
    source_reference = retrieved_chunk.to_source_reference()

    pprint(chunk_dict)
    pprint(retrieved_dict)
    pprint(source_reference)

    checks = [
        chunk.collection_name == DEFAULT_COLLECTION_NAME,
        chunk.content_hash == sha256_text(content),
        chunk.allow_commitment_reference is False,
        chunk_dict["sku_scope"] == ["SKU001"],
        retrieved_chunk.score == 0.82,
        retrieved_dict["module"] == "quality",
        source_reference["source_type"] == "rag_chunk",
        source_reference["reference_id"] == "contract_quality_chunk_001",
        source_reference["collection"] == DEFAULT_COLLECTION_NAME,
    ]

    return all(checks)


def check_retrieved_chunk_schema() -> bool:
    """Check RetrievedChunk contract."""

    print("=" * 80)
    print("checking RetrievedChunk schema")

    chunk = RetrievedChunk(
        collection="kb_chunks_v1",
        chunk_id="retrieved_contract_001",
        source_type="manual_doc",
        source_name="rag_contract_check",
        doc_id="doc_001",
        doc_title="RAG Contract",
        chunk_index=0,
        module="general",
        content="RAG 只作为补充说明来源，不作为业务承诺来源。",
        score=0.91,
        is_verified=True,
    )

    result = RetrievalResult(
        chunks=[chunk],
        rejected_chunks=[],
        warnings=[],
        metadata={
            "retrieval_mode": "contract_test",
        },
    )

    chunk_dicts = result.to_retrieved_chunk_dicts()
    source_references = result.to_source_references()

    pprint(chunk_dicts)
    pprint(source_references)

    checks = [
        len(chunk_dicts) == 1,
        chunk_dicts[0]["chunk_id"] == "retrieved_contract_001",
        len(source_references) == 1,
        source_references[0]["source_type"] == "rag_chunk",
        source_references[0]["score"] == 0.91,
    ]

    return all(checks)


def check_retrieval_query_validation() -> bool:
    """Check RetrievalQuery validation."""

    print("=" * 80)
    print("checking RetrievalQuery validation")

    valid_query = RetrievalQuery(
        query="SKU001 表面处理说明",
        selected_module="quality",
        matched_sku="SKU001",
        top_k=5,
        min_score=0.2,
    )

    invalid_cases_passed = 0

    invalid_inputs = [
        {
            "query": "   ",
            "selected_module": "quality",
            "matched_sku": None,
            "top_k": 5,
        },
        {
            "query": "SKU001",
            "selected_module": "invalid",
            "matched_sku": None,
            "top_k": 5,
        },
        {
            "query": "SKU001",
            "selected_module": "quality",
            "matched_sku": None,
            "top_k": 0,
        },
        {
            "query": "SKU001",
            "selected_module": "quality",
            "matched_sku": None,
            "top_k": 51,
        },
    ]

    for item in invalid_inputs:
        try:
            RetrievalQuery(**item)
        except ValueError:
            invalid_cases_passed += 1

    pprint(valid_query)

    checks = [
        valid_query.normalized_query == "SKU001 表面处理说明",
        invalid_cases_passed == len(invalid_inputs),
    ]

    return all(checks)


def check_embedding_client_contract() -> bool:
    """Check deterministic embedding client contract."""

    print("=" * 80)
    print("checking embedding client contract")

    client = DeterministicHashEmbeddingClient(dimension=8)

    vector_a = client.embed_query("SKU001 表面处理说明")
    vector_b = client.embed_query("SKU001 表面处理说明")
    vector_c = client.embed_query("SKU001 物流说明")

    pprint(vector_a)
    pprint(vector_c)

    validate_embedding_vector(
        vector_a,
        expected_dimension=8,
    )

    blank_rejected = False

    try:
        client.embed_query("   ")
    except ValueError:
        blank_rejected = True

    checks = [
        len(vector_a) == 8,
        vector_a == vector_b,
        vector_a != vector_c,
        all(isinstance(item, float) for item in vector_a),
        blank_rejected,
    ]

    return all(checks)


def check_null_retriever_contract() -> bool:
    """Check NullRetriever behavior."""

    print("=" * 80)
    print("checking NullRetriever contract")

    retriever = NullRetriever()

    chunks = retriever.retrieve(
        query="SKU001 表面处理说明",
        selected_module="quality",
        matched_sku="SKU001",
        top_k=5,
    )

    sanitized_chunks = ensure_retrieved_chunk_dicts(chunks)

    blank_rejected = False

    try:
        retriever.retrieve(
            query="   ",
            selected_module="quality",
            matched_sku=None,
            top_k=5,
        )
    except ValueError:
        blank_rejected = True

    pprint(chunks)
    pprint(sanitized_chunks)

    checks = [
        chunks == [],
        sanitized_chunks == [],
        blank_rejected,
        retriever.reason == "retrieval_disabled",
    ]

    return all(checks)


def check_no_forbidden_commitment_fragments() -> bool:
    """Check contract objects do not generate forbidden commitment fragments."""

    print("=" * 80)
    print("checking forbidden commitment fragments")

    chunk = KnowledgeChunk(
        chunk_id="contract_boundary_chunk_001",
        source_type="manual_doc",
        source_name="rag_contract_check",
        doc_id="boundary_doc",
        doc_title="RAG 边界说明",
        chunk_index=0,
        module="general",
        content="RAG 只作为补充说明来源，不能作为价格、物流、质量、售后承诺来源。",
    )

    serialized = str(chunk.to_dict())

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in serialized:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def main() -> int:
    """Run RAG retriever contract checks."""

    results = [
        check_knowledge_chunk_schema(),
        check_retrieved_chunk_schema(),
        check_retrieval_query_validation(),
        check_embedding_client_contract(),
        check_null_retriever_contract(),
        check_no_forbidden_commitment_fragments(),
    ]

    print("=" * 80)

    if not all(results):
        print("rag retriever contract check failed")
        return 1

    print("rag retriever contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())