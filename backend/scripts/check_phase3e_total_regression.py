"""Phase 3-E total regression check.

This script runs stable baseline checks and all Phase 3-E RAG checks.

It intentionally does not run check_phase3d_total_regression.py because Phase
3-E replaces the Phase 3-D placeholder RetrievalNode with LocalRetriever +
EvidenceFilter. The placeholder-specific assertions are superseded by
check_workflow_rag_integration.py.

It does not call Qdrant, call an LLM, generate answers, promise prices, promise
logistics, promise quality, promise warranty, promise returns/exchanges, or
create business commitments.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RegressionCheck:
    """One regression check command."""

    name: str
    command: list[str]


CHECKS: Final[tuple[RegressionCheck, ...]] = (
    RegressionCheck(
        name="phase3c_total_regression",
        command=[sys.executable, "scripts/check_phase3c_total_regression.py"],
    ),
    RegressionCheck(
        name="langgraph_installation",
        command=[sys.executable, "scripts/check_langgraph_installation.py"],
    ),
    RegressionCheck(
        name="create_knowledge_chunks_table",
        command=[sys.executable, "scripts/create_knowledge_chunks_table.py"],
    ),
    RegressionCheck(
        name="knowledge_chunks_schema",
        command=[sys.executable, "scripts/check_knowledge_chunks_schema.py"],
    ),
    RegressionCheck(
        name="rag_retriever_contract",
        command=[sys.executable, "scripts/check_rag_retriever_contract.py"],
    ),
    RegressionCheck(
        name="rag_evidence_filter",
        command=[sys.executable, "scripts/check_rag_evidence_filter.py"],
    ),
    RegressionCheck(
        name="knowledge_chunk_repository",
        command=[sys.executable, "scripts/check_knowledge_chunk_repository.py"],
    ),
    RegressionCheck(
        name="seed_rag_knowledge_chunks",
        command=[sys.executable, "scripts/seed_rag_knowledge_chunks.py"],
    ),
    RegressionCheck(
        name="rag_seed_knowledge_chunks",
        command=[sys.executable, "scripts/check_rag_seed_knowledge_chunks.py"],
    ),
    RegressionCheck(
        name="local_rag_retriever",
        command=[sys.executable, "scripts/check_local_rag_retriever.py"],
    ),
    RegressionCheck(
        name="workflow_rag_integration",
        command=[sys.executable, "scripts/check_workflow_rag_integration.py"],
    ),
)


def run_check(
    check: RegressionCheck,
) -> bool:
    """Run one regression check."""

    print("=" * 80)
    print(f"running: {check.name}")
    print("command:", " ".join(check.command))

    completed = subprocess.run(
        check.command,
        cwd=BACKEND_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    if completed.stdout:
        print(completed.stdout)

    if completed.stderr:
        print(completed.stderr, file=sys.stderr)

    if completed.returncode != 0:
        print(f"FAILED: {check.name}")
        return False

    print(f"PASSED: {check.name}")
    return True


def main() -> int:
    """Run Phase 3-E total regression."""

    print("phase3-e total regression started")
    print(f"backend root: {BACKEND_ROOT}")

    results: list[tuple[str, bool]] = []

    for check in CHECKS:
        passed = run_check(check)
        results.append((check.name, passed))

        if not passed:
            break

    print("=" * 80)
    print("phase3-e total regression summary")

    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"{status:<8} {name}")

    if not all(passed for _, passed in results):
        print("phase3-e total regression failed")
        return 1

    print("phase3-e total regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())