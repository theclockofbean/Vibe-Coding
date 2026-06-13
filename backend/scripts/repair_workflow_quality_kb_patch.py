"""Repair broken workflow.py patch for Quality KB retrieval."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_FILE = Path("app/agent/workflow.py")


BROKEN_IMPORT = """from app.agent.rag import (
from app.agent.rag.quality_kb_retriever import QualityKBQdrantRetriever
    LocalKnowledgeChunkRetriever,
    filter_retrieved_chunk_dicts,
)
"""

FIXED_IMPORT = """from app.agent.rag import (
    LocalKnowledgeChunkRetriever,
    filter_retrieved_chunk_dicts,
)
from app.agent.rag.quality_kb_retriever import QualityKBQdrantRetriever
"""


BROKEN_SIGNATURE_INSERTION = """    next_state = dict(state)
    next_state, real_quality_kb_used = _try_real_quality_kb_retrieval(next_state)
    if real_quality_kb_used:
        return next_state
        self,
"""

FIXED_SIGNATURE_PART = """        self,
"""


HOOK_AFTER_COPY = """        new_state = _copy_state(state)
"""

QUALITY_HOOK = (
    "        new_state, real_quality_kb_used = _try_real_quality_kb_retrieval("
    "new_state)\n"
    "        if real_quality_kb_used:\n"
    "            return new_state\n\n"
)


def repair_workflow() -> None:
    """Repair workflow.py."""

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    if BROKEN_IMPORT in content:
        content = content.replace(BROKEN_IMPORT, FIXED_IMPORT)

    if BROKEN_SIGNATURE_INSERTION in content:
        content = content.replace(BROKEN_SIGNATURE_INSERTION, FIXED_SIGNATURE_PART)

    if QUALITY_HOOK not in content:
        if HOOK_AFTER_COPY not in content:
            raise RuntimeError(
                "Could not find RetrievalNode body marker: "
                "new_state = _copy_state(state)"
            )

        content = content.replace(
            HOOK_AFTER_COPY,
            HOOK_AFTER_COPY + QUALITY_HOOK,
            1,
        )

    if "_try_real_quality_kb_retrieval" not in content:
        raise RuntimeError("quality retrieval helpers are missing from workflow.py")

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    if content == original:
        print("workflow.py unchanged; nothing repaired")
    else:
        print("workflow.py repaired")


if __name__ == "__main__":
    repair_workflow()