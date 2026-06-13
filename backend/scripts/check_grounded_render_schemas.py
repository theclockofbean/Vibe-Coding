# ruff: noqa: E402,I001
"""Check grounded render schemas."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.rendering.schemas import (
    DEFAULT_RENDER_BUSINESS_RULES,
    SAFE_FALLBACK_RESPONSE,
    SAFETY_BLOCKED_RESPONSE,
    GroundedRenderContractError,
    GroundedRenderInput,
    GroundedRenderOutput,
    make_response_source,
)


def check_render_input_schema() -> bool:
    """Check GroundedRenderInput."""

    print("=" * 80)
    print("checking GroundedRenderInput")

    render_input = GroundedRenderInput(
        session_id="render-schema-session",
        user_text="SKU001 材质说明",
        selected_module="quality",
        handler_status="success",
        answer_text="结构化答复",
        structured_facts={
            "sku_id": "SKU001",
            "material": "铝合金6061",
        },
        retrieved_chunks=[
            {
                "chunk_id": "seed_quality_material_6061",
                "allow_answer_reference": True,
            }
        ],
        source_references=[
            {
                "source_type": "products",
                "reference_id": "SKU001",
            }
        ],
        llm_output="安全表达补充",
        llm_response={
            "is_safe": True,
            "error": None,
            "metadata": {
                "fact_source_allowed": False,
                "commitment_source_allowed": False,
            },
        },
    )

    pprint(render_input.to_dict())

    checks = [
        render_input.selected_module == "quality",
        render_input.structured_facts["sku_id"] == "SKU001",
        len(render_input.business_rules) == len(DEFAULT_RENDER_BUSINESS_RULES),
        render_input.to_dict()["answer_text"] == "结构化答复",
    ]

    return all(checks)


def check_render_output_schema() -> bool:
    """Check GroundedRenderOutput."""

    print("=" * 80)
    print("checking GroundedRenderOutput")

    source = make_response_source(
        reference_id="SKU001",
        source_type="products",
        source_name="products",
        used_for="structured_fact",
    )

    output = GroundedRenderOutput(
        final_response="结构化最终答复。",
        response_sources=[source],
        response_warnings=[],
        is_grounded=True,
        used_llm_output=False,
        needs_handoff=False,
    )

    pprint(output.to_dict())

    checks = [
        output.final_response == "结构化最终答复。",
        output.response_sources[0]["used_for"] == "structured_fact",
        output.is_grounded is True,
        output.needs_handoff is False,
    ]

    return all(checks)


def check_invalid_output_rejected() -> bool:
    """Check blank final_response is rejected."""

    print("=" * 80)
    print("checking invalid output rejected")

    try:
        GroundedRenderOutput(final_response="")
    except GroundedRenderContractError as exc:
        print(str(exc))
        return True

    return False


def check_fallback_templates() -> bool:
    """Check fallback templates exist."""

    print("=" * 80)
    print("checking fallback templates")

    pprint(
        {
            "safe_fallback": SAFE_FALLBACK_RESPONSE,
            "safety_blocked": SAFETY_BLOCKED_RESPONSE,
        }
    )

    checks = [
        "当前信息不足" in SAFE_FALLBACK_RESPONSE,
        "未经授权的业务承诺" in SAFETY_BLOCKED_RESPONSE,
    ]

    return all(checks)


def main() -> int:
    """Run schema checks."""

    results = [
        check_render_input_schema(),
        check_render_output_schema(),
        check_invalid_output_rejected(),
        check_fallback_templates(),
    ]

    print("=" * 80)

    if not all(results):
        print("grounded render schemas check failed")
        return 1

    print("grounded render schemas check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())