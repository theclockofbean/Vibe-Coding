"""Patch workflow.py to use real Quality KB retriever for quality module."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def patch_workflow() -> None:
    """Patch workflow.py."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    original_content = content

    content = ensure_import(content)
    content = ensure_helpers(content)
    content = patch_retrieval_node(content)

    if content == original_content:
        print("workflow.py unchanged; patch may already be applied")
        return

    WORKFLOW_FILE.write_text(content, encoding="utf-8")
    print("workflow.py patched for real Quality KB retrieval")


def ensure_import(content: str) -> str:
    """Ensure QualityKBQdrantRetriever import exists."""

    import_line = (
        "from app.agent.rag.quality_kb_retriever import "
        "QualityKBQdrantRetriever\n"
    )

    if import_line in content:
        return content

    lines = content.splitlines(keepends=True)

    insert_index = 0

    for index, line in enumerate(lines):
        if line.startswith("from app.agent.rag"):
            insert_index = index + 1

    if insert_index == 0:
        for index, line in enumerate(lines):
            if line.startswith("from app."):
                insert_index = index + 1

    lines.insert(insert_index, import_line)

    return "".join(lines)


def ensure_helpers(content: str) -> str:
    """Append helper functions if missing."""

    if "_try_real_quality_kb_retrieval" in content:
        return content

    helper = r'''

def _workflow_env_bool(
    name: str,
    *,
    default: bool = False,
) -> bool:
    """Read boolean env flag for workflow."""

    import os

    value = os.getenv(name, "").strip().lower()

    if not value:
        return default

    return value in {"1", "true", "yes", "on"}


def _state_current_module_for_quality_retrieval(
    state: dict,
) -> str:
    """Return current module from workflow state."""

    for key in ("selected_module", "intent", "workflow_route"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    metadata = state.get("metadata")

    if isinstance(metadata, dict):
        for key in (
            "llm_intent_applied_intent",
            "llm_intent",
            "retrieval_selected_module",
        ):
            value = metadata.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip().lower()

    return ""


def _state_current_query_for_quality_retrieval(
    state: dict,
) -> str:
    """Return current query text from workflow state."""

    for key in ("current_message", "user_message", "query", "message"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = state.get("messages")

    if isinstance(messages, list) and messages:
        last_message = messages[-1]

        if isinstance(last_message, dict):
            content = last_message.get("content")

            if isinstance(content, str) and content.strip():
                return content.strip()

        if isinstance(last_message, str) and last_message.strip():
            return last_message.strip()

    return ""


def _try_real_quality_kb_retrieval(
    state: dict,
) -> tuple[dict, bool]:
    """Try real Quality KB retrieval and return updated state plus success."""

    if not _workflow_env_bool("QUALITY_KB_RETRIEVER_ENABLED", default=True):
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = False

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    current_module = _state_current_module_for_quality_retrieval(state)

    if current_module != "quality":
        return state, False

    query = _state_current_query_for_quality_retrieval(state)

    if not query:
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = True
        metadata["real_quality_kb_retriever_used"] = False
        metadata["real_quality_kb_retriever_error"] = "empty query"

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    try:
        retriever = QualityKBQdrantRetriever.from_env()
        retrieved_payloads = retriever.retrieve_payloads(query)
    except Exception as exc:
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = True
        metadata["real_quality_kb_retriever_used"] = False
        metadata["real_quality_kb_retriever_error"] = (
            f"{type(exc).__name__}: {exc}"
        )

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    if not retrieved_payloads:
        metadata = dict(state.get("metadata") or {})
        metadata["real_quality_kb_retriever_enabled"] = True
        metadata["real_quality_kb_retriever_used"] = False
        metadata["real_quality_kb_retriever_error"] = "no hits"

        next_state = dict(state)
        next_state["metadata"] = metadata

        return next_state, False

    metadata = dict(state.get("metadata") or {})
    metadata["real_quality_kb_retriever_enabled"] = True
    metadata["real_quality_kb_retriever_used"] = True
    metadata["real_quality_kb_retriever_error"] = None
    metadata["retrieval_source"] = "real_quality_kb"
    metadata["retrieval_selected_module"] = "quality"
    metadata["retrieval_collection_name"] = "quality_kb_v1"
    metadata["retrieval_hit_count"] = len(retrieved_payloads)

    next_state = dict(state)
    next_state["metadata"] = metadata
    next_state["retrieved_chunks"] = retrieved_payloads
    next_state["retrieval_selected_module"] = "quality"
    next_state["selected_module"] = "quality"

    return next_state, True
'''

    return content.rstrip() + helper + "\n"


def patch_retrieval_node(content: str) -> str:
    """Patch retrieval node with real quality retrieval hook."""

    marker = "def retrieval_node("
    class_marker = "class RetrievalNode"

    if "_try_real_quality_kb_retrieval(next_state)" in content:
        return content

    if marker in content:
        return patch_function_style_retrieval_node(content)

    if class_marker in content:
        return patch_class_style_retrieval_node(content)

    raise RuntimeError(
        "Could not find retrieval_node function or RetrievalNode class in workflow.py"
    )


def patch_function_style_retrieval_node(content: str) -> str:
    """Patch function-style retrieval_node."""

    marker = "def retrieval_node("
    start = content.find(marker)

    if start < 0:
        raise RuntimeError("retrieval_node function not found")

    body_start = content.find("\n", start)

    if body_start < 0:
        raise RuntimeError("retrieval_node body start not found")

    insertion = (
        "\n"
        "    next_state = dict(state)\n"
        "    next_state, real_quality_kb_used = "
        "_try_real_quality_kb_retrieval(next_state)\n"
        "    if real_quality_kb_used:\n"
        "        return next_state\n"
    )

    return content[: body_start + 1] + insertion + content[body_start + 1 :]


def patch_class_style_retrieval_node(content: str) -> str:
    """Patch class-style RetrievalNode.__call__ or run."""

    class_start = content.find("class RetrievalNode")

    if class_start < 0:
        raise RuntimeError("RetrievalNode class not found")

    search_area = content[class_start:]

    for method_marker in ("    def __call__(", "    def run("):
        relative_method_start = search_area.find(method_marker)

        if relative_method_start < 0:
            continue

        method_start = class_start + relative_method_start
        body_start = content.find("\n", method_start)

        if body_start < 0:
            continue

        insertion = (
            "\n"
            "        next_state = dict(state)\n"
            "        next_state, real_quality_kb_used = "
            "_try_real_quality_kb_retrieval(next_state)\n"
            "        if real_quality_kb_used:\n"
            "            return next_state\n"
        )

        return content[: body_start + 1] + insertion + content[body_start + 1 :]

    raise RuntimeError(
        "RetrievalNode found, but no __call__ or run method could be patched"
    )


if __name__ == "__main__":
    patch_workflow()