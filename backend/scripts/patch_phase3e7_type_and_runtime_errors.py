"""Patch Phase 3-E-7 runtime and mypy issues."""

from __future__ import annotations

from pathlib import Path


def patch_workflow() -> None:
    """Patch workflow retrieval node."""

    target = Path("app/agent/workflow.py")
    content = target.read_text(encoding="utf-8")

    content = content.replace(
        "apply_retrieved_chunks,",
        "",
    )

    content = content.replace(
        """            retriever = NullRetriever(reason="repository_session_unavailable")
            raw_chunks = retriever.retrieve(
                query=user_text,
                selected_module=selected_module,
                matched_sku=matched_sku,
                top_k=5,
            )
""",
        """            null_retriever = NullRetriever(
                reason="repository_session_unavailable",
            )
            raw_chunks = null_retriever.retrieve(
                query=user_text,
                selected_module=selected_module,
                matched_sku=matched_sku,
                top_k=5,
            )
""",
    )

    content = content.replace(
        """            retriever = LocalKnowledgeChunkRetriever(
                session=repository_session,
                score_threshold=0.01,
                max_candidates=50,
            )
            raw_chunks = retriever.retrieve(
                query=user_text,
                selected_module=selected_module,
                matched_sku=matched_sku,
                top_k=5,
            )
""",
        """            local_retriever = LocalKnowledgeChunkRetriever(
                session=repository_session,
                score_threshold=0.01,
                max_candidates=50,
            )
            raw_chunks = local_retriever.retrieve(
                query=user_text,
                selected_module=selected_module,
                matched_sku=matched_sku,
                top_k=5,
            )
""",
    )

    content = content.replace(
        """            apply_retrieved_chunks(new_state, [])
""",
        """            new_state["retrieved_chunks"] = []
""",
    )

    content = content.replace(
        """        apply_retrieved_chunks(
            new_state,
            safe_chunk_dicts,
        )
""",
        """        new_state["retrieved_chunks"] = safe_chunk_dicts
""",
    )

    target.write_text(content, encoding="utf-8")
    print("patched workflow.py")


def patch_knowledge_chunk_repository() -> None:
    """Patch RowMapping typing issue."""

    target = Path("app/repositories/knowledge_chunk_repository.py")
    content = target.read_text(encoding="utf-8")

    content = content.replace(
        "from collections.abc import Mapping\n",
        "",
    )

    content = content.replace(
        """def _row_to_dict(
    row: Mapping[str, Any],
) -> dict[str, Any]:
""",
        """def _row_to_dict(
    row: Any,
) -> dict[str, Any]:
""",
    )

    target.write_text(content, encoding="utf-8")
    print("patched knowledge_chunk_repository.py")


def patch_conversation_repository() -> None:
    """Patch mypy optional int issue if present."""

    target = Path("app/repositories/conversation_repository.py")
    content = target.read_text(encoding="utf-8")
    lines = content.splitlines()

    patched = False

    start = max(0, 540)
    end = min(len(lines), 590)

    for index in range(start, end):
        stripped = lines[index].strip()

        if stripped.startswith("return int(") and stripped.endswith(")"):
            indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
            inner = stripped[len("return int(") : -1]
            lines[index] = f"{indent}return _safe_int_or_none({inner})"
            patched = True
            break

    content = "\n".join(lines) + "\n"

    if patched and "def _safe_int_or_none(" not in content:
        helper = '''

def _safe_int_or_none(
    value: object,
) -> int | None:
    """Safely convert database scalar to optional int."""

    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.strip():
        return int(value)

    return None
'''
        content = content.rstrip() + helper + "\n"

    target.write_text(content, encoding="utf-8")

    if patched:
        print("patched conversation_repository.py")
    else:
        print("conversation_repository.py did not need patch")


def main() -> int:
    """Run patches."""

    patch_workflow()
    patch_knowledge_chunk_repository()
    patch_conversation_repository()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())