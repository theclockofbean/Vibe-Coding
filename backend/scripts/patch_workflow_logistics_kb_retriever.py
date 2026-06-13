"""Patch workflow.py to use real Logistics KB retriever."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def patch_workflow() -> None:
    """Patch workflow.py with Logistics KB retrieval hook."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    content = ensure_imports(content)
    content = ensure_retrieval_node_hook(content)
    content = ensure_helper_functions(content)

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print("workflow.py Logistics KB retriever patch applied")


def ensure_imports(content: str) -> str:
    """Ensure required imports exist."""

    if "import os\n" not in content:
        content = content.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nimport os\n",
            1,
        )

    logistics_import = (
        "from app.agent.rag.logistics_kb_retriever import "
        "LogisticsKBQdrantRetriever\n"
    )

    if logistics_import in content:
        return content

    quality_import = (
        "from app.agent.rag.quality_kb_retriever import "
        "QualityKBQdrantRetriever\n"
    )

    if quality_import not in content:
        raise RuntimeError("QualityKBQdrantRetriever import not found")

    return content.replace(
        quality_import,
        quality_import + logistics_import,
        1,
    )


def ensure_retrieval_node_hook(content: str) -> str:
    """Insert Logistics KB retrieval hook after Quality KB hook."""

    if "real_logistics_kb_used" in content:
        return content

    anchor = "    new_state = cast(AgentState, quality_state)\n"

    insert = (
        anchor
        + "    logistics_state, real_logistics_kb_used = "
        + "_try_real_logistics_kb_retrieval(dict(new_state))\n"
        + "    if real_logistics_kb_used:\n"
        + "        return cast(AgentState, logistics_state)\n"
        + "    new_state = cast(AgentState, logistics_state)\n"
    )

    if anchor not in content:
        raise RuntimeError("quality retrieval hook anchor not found")

    return content.replace(anchor, insert, 1)


def ensure_helper_functions(content: str) -> str:
    """Append Logistics KB helper functions."""

    if "def _try_real_logistics_kb_retrieval" in content:
        return content

    helper_block = r'''


def _try_real_logistics_kb_retrieval(
    state: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Try real Logistics KB retrieval for logistics module."""

    metadata = _state_metadata_for_logistics_retrieval(state)

    selected_module = str(
        state.get("selected_module")
        or state.get("intent")
        or ""
    ).strip().lower()

    if selected_module != "logistics":
        return state, False

    enabled = _logistics_kb_retriever_enabled_from_env()
    metadata["real_logistics_kb_retriever_enabled"] = enabled

    if not enabled:
        metadata["real_logistics_kb_retriever_used"] = False
        metadata["real_logistics_kb_retriever_error"] = "disabled"
        return state, False

    query = _state_current_query_for_logistics_retrieval(state)

    if not query:
        metadata["real_logistics_kb_retriever_used"] = False
        metadata["real_logistics_kb_retriever_error"] = "empty query"
        return state, False

    try:
        retriever = LogisticsKBQdrantRetriever.from_env()
        chunks = retriever.retrieve_chunks(
            query,
            top_k=_logistics_kb_top_k_from_env(),
        )
    except Exception as exc:
        metadata["real_logistics_kb_retriever_used"] = False
        metadata["real_logistics_kb_retriever_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        return state, False

    if not chunks:
        metadata["real_logistics_kb_retriever_used"] = False
        metadata["real_logistics_kb_retriever_error"] = "no hits"
        return state, False

    state["retrieved_chunks"] = chunks
    metadata["real_logistics_kb_retriever_used"] = True
    metadata["real_logistics_kb_retriever_error"] = None
    metadata["retrieval_source"] = "real_logistics_kb"
    metadata["retrieval_selected_module"] = "logistics"
    metadata["retrieval_collection_name"] = retriever.collection_name
    metadata["retrieval_hit_count"] = len(chunks)

    return state, True


def _state_metadata_for_logistics_retrieval(
    state: dict[str, Any],
) -> dict[str, Any]:
    """Return mutable metadata dict from state."""

    metadata = state.get("metadata")

    if isinstance(metadata, dict):
        return metadata

    metadata = {}
    state["metadata"] = metadata

    return metadata


def _state_current_query_for_logistics_retrieval(
    state: dict[str, Any],
) -> str:
    """Extract query text for real Logistics KB retrieval."""

    for key in (
        "user_text",
        "current_message",
        "user_message",
        "query",
        "message",
    ):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _logistics_kb_retriever_enabled_from_env() -> bool:
    """Return whether real Logistics KB retriever is enabled."""

    value = os.getenv("LOGISTICS_KB_RETRIEVER_ENABLED", "1").strip().lower()

    return value not in {"0", "false", "no", "off"}


def _logistics_kb_top_k_from_env() -> int:
    """Return Logistics KB top-k from env."""

    value = os.getenv("LOGISTICS_KB_TOP_K", "5").strip()

    if not value:
        return 5

    return int(value)
'''

    return content.rstrip() + helper_block + "\n"


if __name__ == "__main__":
    patch_workflow()