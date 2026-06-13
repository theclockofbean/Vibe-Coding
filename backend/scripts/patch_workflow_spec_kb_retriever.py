"""Patch workflow.py to integrate real Spec KB retriever."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


PRICE_HOOK_ANCHOR: Final[str] = "\n".join(
    [
        "        price_state, real_price_kb_used = _try_real_price_kb_retrieval(dict(new_state))",
        "        if real_price_kb_used:",
        "            return price_state",
        "        new_state = price_state",
        "",
    ]
)

SPEC_HOOK_BLOCK: Final[str] = "\n".join(
    [
        "        spec_state, real_spec_kb_used = _try_real_spec_kb_retrieval(dict(new_state))",
        "        if real_spec_kb_used:",
        "            return spec_state",
        "        new_state = spec_state",
        "",
    ]
)


SPEC_HELPERS: Final[str] = '''
def _try_real_spec_kb_retrieval(
    state: dict[str, Any],
) -> tuple[AgentState, bool]:
    """Try real Spec KB retrieval."""

    import os

    from app.agent.rag.spec_kb_retriever import SpecKBQdrantRetriever
    from app.agent.rag.spec_kb_retriever import SpecKBQdrantRetrieverConfig

    new_state = cast(AgentState, dict(state))
    metadata = _ensure_metadata(new_state)

    enabled = _spec_kb_retriever_enabled_from_env()
    metadata["real_spec_kb_retriever_enabled"] = enabled
    metadata["real_spec_kb_retriever_used"] = False
    metadata["real_spec_kb_retriever_error"] = None

    selected_module = str(
        new_state.get("selected_module")
        or new_state.get("intent")
        or ""
    ).strip().lower()

    candidate_modules_value = new_state.get("candidate_modules") or []
    candidate_modules: list[str] = []

    if isinstance(candidate_modules_value, list):
        candidate_modules = [
            str(item).strip().lower()
            for item in candidate_modules_value
            if str(item).strip()
        ]

    if selected_module != "spec" and "spec" not in candidate_modules:
        return new_state, False

    query = _state_current_query_for_spec_retrieval(new_state)

    if not enabled or not query:
        return new_state, False

    try:
        collection_name = os.getenv("QDRANT_COLLECTION_SPEC", "spec_kb_v1")
        top_k = _spec_kb_top_k_from_env()
        config = SpecKBQdrantRetrieverConfig.from_env()
        config = SpecKBQdrantRetrieverConfig(
            collection_name=collection_name,
            qdrant_url=config.qdrant_url,
            embedding_base_url=config.embedding_base_url,
            embedding_timeout_seconds=config.embedding_timeout_seconds,
            top_k=top_k,
        )
        retriever = SpecKBQdrantRetriever(config=config)
        chunks = retriever.retrieve(query=query, top_k=top_k)

        if not chunks:
            metadata["real_spec_kb_retriever_error"] = "empty retrieval result"
            return new_state, False

        retrieved_chunks = [chunk.to_context() for chunk in chunks]
        new_state["retrieved_chunks"] = retrieved_chunks
        new_state["retrieval_context"] = retrieved_chunks
        new_state["retrieval_source"] = "real_spec_kb"
        new_state["retrieval_collection_name"] = collection_name

        metadata["real_spec_kb_retriever_used"] = True
        metadata["real_spec_kb_retriever_hit_count"] = len(retrieved_chunks)
        metadata["real_spec_kb_retriever_collection_name"] = collection_name
        metadata["real_spec_kb_retriever_top_k"] = top_k
        metadata["retrieval_source"] = "real_spec_kb"
        metadata["retrieval_collection_name"] = collection_name

        return new_state, True

    except Exception as exc:
        metadata["real_spec_kb_retriever_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        return new_state, False


def _state_current_query_for_spec_retrieval(
    state: AgentState,
) -> str:
    """Return current query text for Spec KB retrieval."""

    for key in ("user_text", "current_message", "user_message", "query"):
        value = state.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _spec_kb_retriever_enabled_from_env() -> bool:
    """Return whether real Spec KB retriever is enabled."""

    import os

    value = os.getenv("SPEC_KB_RETRIEVER_ENABLED", "1").strip().lower()

    return value not in {"0", "false", "no", "off"}


def _spec_kb_top_k_from_env() -> int:
    """Return Spec KB top-k from env."""

    import os

    value = os.getenv("SPEC_KB_TOP_K", "5").strip()

    if not value:
        return 5

    top_k = int(value)

    if top_k <= 0:
        return 5

    return top_k
'''


def main() -> int:
    """Patch workflow.py."""

    print("=" * 80)
    print("patching workflow.py for Spec KB retriever")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    if "_try_real_spec_kb_retrieval" in content:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "already_patched": True,
                "changed": False,
            }
        )
        return 0

    if PRICE_HOOK_ANCHOR not in content:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "error": "price hook anchor not found",
                "hint": "inspect workflow.py around real_price_kb_used",
            }
        )
        return 1

    content = content.replace(
        PRICE_HOOK_ANCHOR,
        PRICE_HOOK_ANCHOR + SPEC_HOOK_BLOCK,
        1,
    )

    content = content.rstrip() + "\n\n\n" + SPEC_HELPERS.strip() + "\n"

    if content == original:
        pprint({"workflow_file": str(WORKFLOW_FILE), "error": "content unchanged"})
        return 1

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "changed": True,
            "inserted_hook": True,
            "inserted_helpers": [
                "_try_real_spec_kb_retrieval",
                "_state_current_query_for_spec_retrieval",
                "_spec_kb_retriever_enabled_from_env",
                "_spec_kb_top_k_from_env",
            ],
        }
    )

    print("workflow.py Spec KB patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())