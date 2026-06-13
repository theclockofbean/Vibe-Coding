"""Fix Spec KB workflow metadata and route override for grounded E2E."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


SPEC_HOOK_ANCHOR: Final[str] = "\n".join(
    [
        "        spec_state, real_spec_kb_used = _try_real_spec_kb_retrieval(dict(new_state))",
        "        if real_spec_kb_used:",
        "            return spec_state",
        "        new_state = spec_state",
    ]
)

SPEC_HOOK_WITH_ROUTE: Final[str] = "\n".join(
    [
        "        new_state = _force_spec_route_for_spec_kb_question(new_state)",
        "        spec_state, real_spec_kb_used = _try_real_spec_kb_retrieval(dict(new_state))",
        "        if real_spec_kb_used:",
        "            return spec_state",
        "        new_state = spec_state",
    ]
)

OLD_METADATA_BLOCK: Final[str] = "\n".join(
    [
        '        metadata["real_spec_kb_retriever_used"] = True',
        '        metadata["real_spec_kb_retriever_hit_count"] = len(retrieved_chunks)',
        '        metadata["real_spec_kb_retriever_collection_name"] = collection_name',
        '        metadata["real_spec_kb_retriever_top_k"] = top_k',
        '        metadata["retrieval_source"] = "real_spec_kb"',
        '        metadata["retrieval_collection_name"] = collection_name',
    ]
)

NEW_METADATA_BLOCK: Final[str] = "\n".join(
    [
        '        metadata["real_spec_kb_retriever_used"] = True',
        '        metadata["real_spec_kb_retriever_hit_count"] = len(retrieved_chunks)',
        '        metadata["real_spec_kb_retriever_collection_name"] = collection_name',
        '        metadata["real_spec_kb_retriever_top_k"] = top_k',
        '        metadata["retrieval_source"] = "real_spec_kb"',
        '        metadata["retrieval_collection_name"] = collection_name',
        '        metadata["retrieval_selected_module"] = "spec"',
        '        metadata["retrieval_hit_count"] = len(retrieved_chunks)',
    ]
)

OLD_STATE_EXTRAS_BLOCK: Final[str] = "\n".join(
    [
        '        cast(dict[str, Any], new_state)["retrieval_context"] = retrieved_chunks',
        '        cast(dict[str, Any], new_state)["retrieval_source"] = "real_spec_kb"',
        '        cast(dict[str, Any], new_state)["retrieval_collection_name"] = collection_name',
    ]
)

NEW_STATE_EXTRAS_BLOCK: Final[str] = "\n".join(
    [
        '        cast(dict[str, Any], new_state)["retrieval_context"] = retrieved_chunks',
        '        cast(dict[str, Any], new_state)["retrieval_source"] = "real_spec_kb"',
        '        cast(dict[str, Any], new_state)["retrieval_collection_name"] = collection_name',
        '        cast(dict[str, Any], new_state)["retrieval_selected_module"] = "spec"',
    ]
)

SPEC_ROUTE_HELPER: Final[str] = '''
def _force_spec_route_for_spec_kb_question(
    state: AgentState,
) -> AgentState:
    """Force spec route for clear Spec KB questions."""

    new_state = cast(AgentState, dict(state))
    metadata = _ensure_metadata(new_state)
    query = _state_current_query_for_spec_retrieval(new_state)
    normalized_query = query.strip().lower()

    if not normalized_query:
        return new_state

    spec_signals = (
        "sku",
        "oem",
        "螺纹",
        "规格",
        "球径",
        "杆长",
        "锥度",
        "材质",
        "表面处理",
        "适配",
        "通用",
        "m8",
        "m10",
        "m12",
    )

    if not any(signal in normalized_query for signal in spec_signals):
        return new_state

    new_state["selected_module"] = "spec"
    new_state["intent"] = "spec"
    new_state["candidate_modules"] = ["spec"]

    metadata["spec_route_override_used"] = True
    metadata["spec_route_override_reason"] = "spec_kb_signal"

    return new_state
'''


def main() -> int:
    """Patch workflow.py."""

    print("=" * 80)
    print("fixing workflow.py Spec KB E2E metadata and route")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    if "_force_spec_route_for_spec_kb_question" not in content:
        if SPEC_HOOK_ANCHOR not in content:
            pprint({"error": "Spec hook anchor not found"})
            return 1

        content = content.replace(SPEC_HOOK_ANCHOR, SPEC_HOOK_WITH_ROUTE, 1)
        content = content.rstrip() + "\n\n\n" + SPEC_ROUTE_HELPER.strip() + "\n"
        changes.append("inserted_spec_route_override")

    if OLD_METADATA_BLOCK in content and 'metadata["retrieval_selected_module"]' not in content:
        content = content.replace(OLD_METADATA_BLOCK, NEW_METADATA_BLOCK, 1)
        changes.append("added_spec_metadata_selected_module")

    if (
        OLD_STATE_EXTRAS_BLOCK in content
        and '["retrieval_selected_module"] = "spec"' not in content
    ):
        content = content.replace(OLD_STATE_EXTRAS_BLOCK, NEW_STATE_EXTRAS_BLOCK, 1)
        changes.append("added_spec_state_extra_selected_module")

    if content == original:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "changed": False,
                "message": "no changes needed or patterns not matched",
            }
        )
        return 0

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "changed": True,
            "changes": changes,
        }
    )

    print("workflow.py Spec KB E2E fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())