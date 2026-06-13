# ruff: noqa: E402,I001
"""Seed initial RAG knowledge chunks.

This script writes deterministic seed chunks into PostgreSQL metadata storage.

It does not call Qdrant, call an LLM, generate embeddings, generate answers,
promise prices, promise logistics, promise quality, promise warranty, promise
returns/exchanges, or create business commitments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from sqlalchemy import text

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rag import KnowledgeChunk
from app.core.database import get_session_factory
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository


SEED_SOURCE_NAME: Final[str] = "phase3e_seed_knowledge"


def build_seed_chunks() -> list[KnowledgeChunk]:
    """Build deterministic seed chunks."""

    return [
        KnowledgeChunk(
            chunk_id="seed_general_rag_boundary",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/rag-boundary",
            doc_id="rag_boundary_v1",
            doc_title="RAG 使用边界说明",
            chunk_index=0,
            module="general",
            content=(
                "RAG 只作为补充说明来源，不作为价格、库存、物流、质量、"
                "售后等业务承诺来源。涉及承诺的问题必须以结构化规则、"
                "正式数据或人工确认为准。"
            ),
            summary="RAG 使用边界。",
            risk_level="low",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "boundary",
            },
        ),
        KnowledgeChunk(
            chunk_id="seed_spec_parameter_boundary",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/spec-boundary",
            doc_id="spec_boundary_v1",
            doc_title="规格参数边界说明",
            chunk_index=0,
            module="spec",
            content=(
                "规格参数应优先以结构化商品资料为准。RAG 可以解释参数含义，"
                "但不能替代 SKU 主数据、OEM 字段、螺纹字段或人工确认结果。"
            ),
            summary="规格参数以结构化商品资料为准。",
            risk_level="low",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "spec",
            },
        ),
        KnowledgeChunk(
            chunk_id="seed_quality_material_6061",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/material-6061",
            doc_id="quality_material_v1",
            doc_title="铝合金 6061 材料说明",
            chunk_index=0,
            module="quality",
            sku_scope=["SKU001"],
            intent_scope=["material_explanation"],
            content=(
                "铝合金 6061 常用于轻量化零件，通常关注重量、加工性和表面处理"
                "适配性。具体商品材质、适配范围和质量结论必须以结构化商品资料、"
                "检测记录或人工确认为准。"
            ),
            summary="铝合金 6061 的一般说明，不作为质量承诺。",
            risk_level="medium",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "material",
            },
        ),
        KnowledgeChunk(
            chunk_id="seed_quality_anodized_surface",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/anodized-surface",
            doc_id="quality_surface_v1",
            doc_title="阳极氧化表面处理说明",
            chunk_index=0,
            module="quality",
            sku_scope=["SKU001"],
            intent_scope=["surface_treatment"],
            content=(
                "阳极氧化是一类常见金属表面处理方式，通常用于改善表面观感和"
                "基础防护表现。具体颜色、外观、耐久表现和使用结果不能仅由 RAG "
                "判断，必须以结构化商品资料、检测记录或人工确认为准。"
            ),
            summary="阳极氧化表面处理的一般说明，不作为质量承诺。",
            risk_level="medium",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "surface_treatment",
            },
        ),
        KnowledgeChunk(
            chunk_id="seed_price_boundary",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/price-boundary",
            doc_id="price_boundary_v1",
            doc_title="价格答复边界说明",
            chunk_index=0,
            module="price",
            content=(
                "报价、折扣、最终成交价格和有效期必须以正式价格表、授权报价"
                "或人工确认为准。RAG 只能说明价格问题的处理边界，不能生成或确认价格。"
            ),
            summary="价格必须由正式价格表或人工确认。",
            risk_level="high",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "price_boundary",
            },
        ),
        KnowledgeChunk(
            chunk_id="seed_logistics_boundary",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/logistics-boundary",
            doc_id="logistics_boundary_v1",
            doc_title="物流答复边界说明",
            chunk_index=0,
            module="logistics",
            content=(
                "物流时效、承运商、运费和配送范围需要结合库存状态、发货地、"
                "订单地址、承运商规则和人工确认。RAG 可以说明处理边界，"
                "不能直接形成发货或到货承诺。"
            ),
            summary="物流问题需结合结构化规则和人工确认。",
            risk_level="high",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "logistics_boundary",
            },
        ),
        KnowledgeChunk(
            chunk_id="seed_aftersale_boundary",
            source_type="manual_doc",
            source_name=SEED_SOURCE_NAME,
            source_uri="manual://phase3e/aftersale-boundary",
            doc_id="aftersale_boundary_v1",
            doc_title="售后答复边界说明",
            chunk_index=0,
            module="general",
            content=(
                "退换、补发、赔付和质保类问题属于高风险业务承诺场景，应进入"
                "人工确认或依据正式售后规则处理。RAG 只能说明边界，不能直接给出承诺。"
            ),
            summary="售后承诺类问题应人工确认或依据正式规则。",
            risk_level="high",
            is_verified=True,
            allow_answer_reference=True,
            allow_commitment_reference=False,
            metadata={
                "phase": "3-E",
                "category": "aftersale_boundary",
            },
        ),
    ]


def cleanup_existing_seed_rows() -> None:
    """Remove previous seed rows for deterministic seeding."""

    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            session.execute(
                text(
                    """
                    DELETE FROM knowledge_chunks
                    WHERE source_name = :source_name;
                    """
                ),
                {
                    "source_name": SEED_SOURCE_NAME,
                },
            )


def seed_chunks() -> list[dict[str, object]]:
    """Seed knowledge chunks."""

    chunks = build_seed_chunks()
    session_factory = get_session_factory()

    with session_factory() as session:
        with session.begin():
            repository = KnowledgeChunkRepository(session)

            rows = [
                repository.upsert_chunk(chunk)
                for chunk in chunks
            ]

    return rows


def main() -> int:
    """Run seed."""

    cleanup_existing_seed_rows()
    rows = seed_chunks()

    print(f"seeded rag knowledge chunks: {len(rows)}")

    for row in rows:
        print(
            f"- {row['chunk_id']} "
            f"module={row['module']} "
            f"risk={row['risk_level']} "
            f"commitment={row['allow_commitment_reference']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())