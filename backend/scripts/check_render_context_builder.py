# ruff: noqa: E402,I001
"""Check RenderContextBuilder."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rendering.context import RenderContextBuilder


def build_sample_state() -> dict[str, Any]:
    """Build sample AgentState-like dict."""

    return {
        "session_id": "render-context-session",
        "user_text": "SKU001 阳极氧化 表面处理 材质说明",
        "selected_module": "quality",
        "handler_status": "success",
        "parse_status": "parsed",
        "route_status": "routed",
        "handoff_required": False,
        "answer_text": "查到 SKU001：材质为铝合金6061，表面处理为阳极氧化黑色。",
        "module_payload": {
            "answer_text": "查到 SKU001：材质为铝合金6061，表面处理为阳极氧化黑色。",
            "query_type": "sku_id",
            "query_value": "SKU001",
            "product_reference_value": "SKU001",
            "material": "铝合金6061",
            "surface_treatment": "阳极氧化黑色",
            "errors": [],
            "warnings": [],
            "source_references": [
                {
                    "source_table": "products",
                    "query_value": "SKU001",
                }
            ],
        },
        "retrieved_chunks": [
            {
                "chunk_id": "seed_quality_material_6061",
                "collection": "kb_chunks_v1",
                "source_type": "manual_doc",
                "source_name": "phase3e_seed_knowledge",
                "doc_title": "铝合金 6061 材料说明",
                "module": "quality",
                "score": 0.99,
                "content": "铝合金 6061 常用于轻量化零件。",
                "summary": "铝合金 6061 的一般说明，不作为质量承诺。",
                "is_active": True,
                "allow_answer_reference": True,
                "allow_commitment_reference": False,
            },
            {
                "chunk_id": "inactive_chunk",
                "is_active": False,
                "allow_answer_reference": True,
            },
            {
                "chunk_id": "not_allowed_chunk",
                "is_active": True,
                "allow_answer_reference": False,
            },
        ],
        "source_references": [
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
        "llm_output": "已接收结构化事实与 RAG 证据，仅可用于非承诺性说明。",
        "llm_response": {
            "is_safe": True,
            "error": None,
            "metadata": {
                "final_response_allowed": False,
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
        },
        "risk_reasons": [],
        "warnings": [],
        "metadata": {
            "retrieval_mode": "qdrant",
            "llm_used": True,
        },
    }


def check_context_builder_extracts_core_fields() -> bool:
    """Check core field extraction."""

    print("=" * 80)
    print("checking context builder core extraction")

    state = build_sample_state()
    render_input = RenderContextBuilder().from_state(state)

    pprint(render_input.to_dict())

    checks = [
        render_input.session_id == "render-context-session",
        render_input.user_text == "SKU001 阳极氧化 表面处理 材质说明",
        render_input.selected_module == "quality",
        render_input.answer_text is not None,
        render_input.structured_facts["query_value"] == "SKU001",
        render_input.structured_facts["material"] == "铝合金6061",
        "answer_text" not in render_input.structured_facts,
        "errors" not in render_input.structured_facts,
        len(render_input.retrieved_chunks) == 1,
        render_input.retrieved_chunks[0]["chunk_id"] == "seed_quality_material_6061",
        len(render_input.source_references) == 2,
        render_input.llm_output is not None,
    ]

    return all(checks)


def check_context_builder_source_usage() -> bool:
    """Check source reference usage labels."""

    print("=" * 80)
    print("checking source usage labels")

    state = build_sample_state()
    render_input = RenderContextBuilder().from_state(state)

    pprint(render_input.source_references)

    usage_values = {
        str(reference.get("used_for"))
        for reference in render_input.source_references
    }

    checks = [
        "structured_fact" in usage_values,
        "supplementary_explanation" in usage_values,
        render_input.retrieved_chunks[0]["used_for"] == "supplementary_explanation",
    ]

    return all(checks)


def check_context_builder_blocks_unsafe_llm_output() -> bool:
    """Check unsafe LLM output is not allowed."""

    print("=" * 80)
    print("checking unsafe LLM output blocked")

    state = build_sample_state()
    state["llm_response"] = {
        "is_safe": False,
        "error": None,
        "metadata": {
            "fact_source_allowed": False,
            "commitment_source_allowed": False,
        },
    }

    render_input = RenderContextBuilder().from_state(state)

    pprint(render_input.to_dict())

    checks = [
        render_input.llm_output is None,
        render_input.metadata["render_llm_output_allowed"] is False,
    ]

    return all(checks)


def check_context_builder_does_not_make_llm_fact_source() -> bool:
    """Check LLM is never structured fact source."""

    print("=" * 80)
    print("checking LLM not fact source")

    state = build_sample_state()
    render_input = RenderContextBuilder().from_state(state)

    serialized_facts = str(render_input.structured_facts)

    checks = [
        "已接收结构化事实" not in serialized_facts,
        "llm_output" not in render_input.structured_facts,
        render_input.llm_response["metadata"]["fact_source_allowed"] is False,
    ]

    return all(checks)


def main() -> int:
    """Run context builder checks."""

    results = [
        check_context_builder_extracts_core_fields(),
        check_context_builder_source_usage(),
        check_context_builder_blocks_unsafe_llm_output(),
        check_context_builder_does_not_make_llm_fact_source(),
    ]

    print("=" * 80)

    if not all(results):
        print("render context builder check failed")
        return 1

    print("render context builder check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())