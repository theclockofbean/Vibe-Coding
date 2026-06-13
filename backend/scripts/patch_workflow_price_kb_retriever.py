"""Patch workflow.py to use real Price KB retriever."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


def main() -> int:
    """Patch workflow.py."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    backup_file = WORKFLOW_FILE.with_name(
        f"workflow.before_price_kb_patch_{datetime.now():%Y%m%d_%H%M%S}.py"
    )
    backup_file.write_text(content, encoding="utf-8")

    lines = content.splitlines()

    if "_try_real_price_kb_retrieval" not in content:
        lines = insert_price_retrieval_hook(lines)
        content = "\n".join(lines) + "\n"
        content = append_price_helpers(content)
    else:
        print("workflow.py already contains Price KB helper")

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    print(f"backup={backup_file}")
    print("workflow.py Price KB retrieval patch applied")
    return 0


def insert_price_retrieval_hook(
    lines: list[str],
) -> list[str]:
    """Insert Price KB hook after Logistics KB hook."""

    target = "new_state = cast(AgentState, logistics_state)"

    for index, line in enumerate(lines):
        if line.strip() != target:
            continue

        window = "\n".join(lines[max(0, index - 8) : index + 1])
        if "real_logistics_kb_used" not in window:
            continue

        indent = line[: len(line) - len(line.lstrip())]

        hook_lines = [
            (
                f"{indent}price_state, real_price_kb_used = "
                "_try_real_price_kb_retrieval(dict(new_state))"
            ),
            f"{indent}if real_price_kb_used:",
            f"{indent}    return cast(AgentState, price_state)",
            f"{indent}new_state = cast(AgentState, price_state)",
        ]

        return lines[: index + 1] + hook_lines + lines[index + 1 :]

    raise RuntimeError("target Logistics KB hook anchor not found")


def append_price_helpers(
    content: str,
) -> str:
    """Append Price KB helper functions."""

    helper = r'''


def _try_real_price_kb_retrieval(
    state: dict[str, Any],
) -> tuple[AgentState, bool]:
    """Try real Price KB retrieval."""

    import os

    from app.agent.rag.price_kb_retriever import PriceKBQdrantRetriever

    new_state = cast(AgentState, dict(state))
    metadata = _ensure_metadata(new_state)

    enabled = _price_kb_retriever_enabled_from_env()
    metadata["real_price_kb_retriever_enabled"] = enabled
    metadata["real_price_kb_retriever_used"] = False
    metadata["real_price_kb_retriever_error"] = None

    selected_module = str(
        new_state.get("selected_module")
        or new_state.get("intent")
        or ""
    ).strip().lower()

    candidate_modules_value = new_state.get("candidate_modules")
    candidate_modules: list[str] = []

    if isinstance(candidate_modules_value, list):
        candidate_modules = [
            str(item).strip().lower()
            for item in candidate_modules_value
            if str(item).strip()
        ]

    if selected_module != "price" and "price" not in candidate_modules:
        return new_state, False

    query = _state_current_query_for_price_retrieval(new_state)

    if not enabled or not query:
        return new_state, False

    try:
        collection_name = os.getenv("QDRANT_COLLECTION_PRICE", "price_kb_v1")
        top_k = _price_kb_top_k_from_env()
        retriever = PriceKBQdrantRetriever(
            collection_name=collection_name,
            top_k=top_k,
        )
        chunks = retriever.retrieve(query, top_k=top_k)

        if not chunks:
            metadata["real_price_kb_retriever_error"] = "empty retrieval result"
            return new_state, False

        new_state["retrieved_chunks"] = chunks

        metadata["real_price_kb_retriever_used"] = True
        metadata["retrieval_source"] = "real_price_kb"
        metadata["retrieval_selected_module"] = "price"
        metadata["retrieval_collection_name"] = retriever.collection_name
        metadata["retrieval_hit_count"] = len(chunks)

        return new_state, True

    except Exception as exc:
        metadata["real_price_kb_retriever_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        return new_state, False


def _state_current_query_for_price_retrieval(
    state: AgentState,
) -> str:
    """Return current query text for Price KB retrieval."""

    for key in ("user_text", "current_message", "user_message", "query"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _price_kb_retriever_enabled_from_env() -> bool:
    """Return whether real Price KB retriever is enabled."""

    import os

    value = os.getenv("PRICE_KB_RETRIEVER_ENABLED", "1").strip().lower()

    return value not in {"0", "false", "no", "off"}


def _price_kb_top_k_from_env() -> int:
    """Return Price KB top-k from env."""

    import os

    value = os.getenv("PRICE_KB_TOP_K", "5").strip()

    if not value:
        return 5

    top_k = int(value)

    if top_k <= 0:
        return 5

    return top_k
'''

    return content.rstrip() + helper + "\n"


if __name__ == "__main__":
    raise SystemExit(main())