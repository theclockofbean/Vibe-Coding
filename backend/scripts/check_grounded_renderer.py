# ruff: noqa: E402,I001
"""Check GroundedRenderer behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rendering.grounded_renderer import GroundedRenderer
from app.agent.rendering.schemas import (
    SAFE_FALLBACK_RESPONSE,
    SAFETY_BLOCKED_RESPONSE,
    GroundedRenderInput,
)


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


def build_quality_render_input() -> GroundedRenderInput:
    """Build quality/spec-like render input."""

    return GroundedRenderInput(
        session_id="grounded-render-quality-session",
        user_text="SKU001 阳极氧化 表面处理 材质说明",
        selected_module="quality",
        handler_status="success",
        parse_status="parsed",
        route_status="routed",
        handoff_required=False,
        answer_text="查到 SKU001：材质为铝合金6061，表面处理为阳极氧化黑色。",
        structured_facts={
            "query_value": "SKU001",
            "material": "铝合金6061",
            "surface_treatment": "阳极氧化黑色",
        },
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "source_name": "phase3e_seed_knowledge",
                "doc_title": "铝合金 6061 材料说明",
                "module": "quality",
                "score": 0.99,
                "summary": "铝合金 6061 的一般说明，不作为质量承诺。",
                "allow_answer_reference": True,
                "allow_commitment_reference": False,
            },
            {
                "chunk_id": "seed_quality_anodized_surface",
                "source_name": "phase3e_seed_knowledge",
                "doc_title": "阳极氧化表面处理说明",
                "module": "quality",
                "score": 0.98,
                "summary": "阳极氧化表面处理的一般说明，不作为质量承诺。",
                "allow_answer_reference": True,
                "allow_commitment_reference": False,
            },
        ],
        source_references=[
            {
                "source_table": "products",
                "query_value": "SKU001",
            },
            {
                "source_type": "rag_chunk",
                "reference_id": "seed_quality_material_6061",
                "source_name": "phase3e_seed_knowledge",
                "doc_title": "铝合金 6061 材料说明",
                "module": "quality",
                "score": 0.99,
            },
        ],
        llm_output="已接收结构化事实与 RAG 证据，仅可用于非承诺性说明。",
        llm_response={
            "is_safe": True,
            "error": None,
            "metadata": {
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
        },
    )


def check_quality_grounded_render() -> bool:
    """Check grounded quality render."""

    print("=" * 80)
    print("checking quality grounded render")

    render_input = build_quality_render_input()
    output = GroundedRenderer().render(render_input)

    pprint(output.to_dict())

    source_types = {
        str(source.get("source_type"))
        for source in output.response_sources
    }
    used_for_values = {
        str(source.get("used_for"))
        for source in output.response_sources
    }

    checks = [
        output.is_grounded is True,
        output.needs_handoff is False,
        output.used_llm_output is True,
        "查到 SKU001" in output.final_response,
        "补充说明" in output.final_response,
        "参考来源" in output.final_response,
        "products" in source_types,
        "rag_chunk" in source_types,
        "business_rule" in source_types,
        "llm_safe_rewrite" in source_types,
        "structured_fact" in used_for_values,
        "supplementary_explanation" in used_for_values,
        "expression_support" in used_for_values,
    ]

    return all(checks)


def check_price_render_no_amount_generation() -> bool:
    """Check price render does not generate amount."""

    print("=" * 80)
    print("checking price grounded render")

    render_input = GroundedRenderInput(
        session_id="grounded-render-price-session",
        user_text="SKU001 多少钱",
        selected_module="price",
        handler_status="handoff",
        handoff_required=True,
        answer_text=(
            "这类问题涉及报价。已识别到 SKU：SKU001。当前系统尚未接入正式价格表，"
            "不能直接给出报价。请补充采购数量、定制要求和收货地区后转人工确认。"
        ),
        retrieved_chunks=[
            {
                "chunk_id": "seed_price_boundary",
                "source_name": "phase3e_seed_knowledge",
                "doc_title": "价格答复边界说明",
                "module": "price",
                "summary": "价格必须由正式价格表或人工确认。",
                "allow_answer_reference": True,
                "allow_commitment_reference": False,
            }
        ],
        source_references=[
            {
                "source_type": "rag_chunk",
                "reference_id": "seed_price_boundary",
                "source_name": "phase3e_seed_knowledge",
                "doc_title": "价格答复边界说明",
                "module": "price",
            }
        ],
        llm_output="该问题涉及需要人工确认的信息，请人工结合正式数据与业务规则处理。",
        llm_response={
            "is_safe": True,
            "error": None,
            "metadata": {
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
        },
    )

    output = GroundedRenderer().render(render_input)

    pprint(output.to_dict())

    checks = [
        output.needs_handoff is True,
        output.is_grounded is True,
        "不能直接给出报价" in output.final_response,
        "正式价格表" in output.final_response,
        "99 元" not in output.final_response,
        "￥" not in output.final_response,
        "保证最低价" not in output.final_response,
    ]

    return all(checks)


def check_unsafe_final_response_blocked() -> bool:
    """Check unsafe final response is blocked."""

    print("=" * 80)
    print("checking unsafe final response blocked")

    render_input = GroundedRenderInput(
        session_id="grounded-render-unsafe-session",
        user_text="SKU001 质量怎么样",
        selected_module="quality",
        handler_status="success",
        handoff_required=False,
        answer_text="这个产品质量很好，放心用，保证不生锈。",
    )

    output = GroundedRenderer().render(render_input)

    pprint(output.to_dict())

    checks = [
        output.final_response == SAFETY_BLOCKED_RESPONSE,
        output.is_grounded is False,
        output.needs_handoff is True,
        output.metadata["render_safety_blocked"] is True,
        "forbidden_commitment" in output.risk_flags,
    ]

    return all(checks)


def check_empty_context_fallback() -> bool:
    """Check empty context fallback."""

    print("=" * 80)
    print("checking empty context fallback")

    render_input = GroundedRenderInput(
        session_id="grounded-render-empty-session",
        user_text="",
    )

    output = GroundedRenderer().render(render_input)

    pprint(output.to_dict())

    checks = [
        output.final_response == SAFE_FALLBACK_RESPONSE,
        output.is_grounded is False,
        output.needs_handoff is True,
        output.metadata["render_mode"] == "fallback_safe_response",
    ]

    return all(checks)


def check_no_forbidden_fragment_in_safe_outputs() -> bool:
    """Check safe outputs contain no forbidden fragments."""

    print("=" * 80)
    print("checking no forbidden fragments in safe output")

    output = GroundedRenderer().render(build_quality_render_input())

    if not output.is_grounded:
        return False

    for fragment in FORBIDDEN_COMMITMENT_FRAGMENTS:
        if fragment in output.final_response:
            print(f"failed: forbidden fragment detected: {fragment}")
            return False

    return True


def main() -> int:
    """Run GroundedRenderer checks."""

    results = [
        check_quality_grounded_render(),
        check_price_render_no_amount_generation(),
        check_unsafe_final_response_blocked(),
        check_empty_context_fallback(),
        check_no_forbidden_fragment_in_safe_outputs(),
    ]

    print("=" * 80)

    if not all(results):
        print("grounded renderer check failed")
        return 1

    print("grounded renderer check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())