"""Phase 3-I-B total regression for real Quality KB."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


STATIC_FILES: Final[list[str]] = [
    "app/agent/workflow.py",
    "app/agent/rag/quality_chunk_builder.py",
    "app/agent/rag/real_embedding.py",
    "app/agent/rag/quality_kb_retriever.py",
    "scripts/check_quality_questions_file.py",
    "scripts/check_quality_kb_chunk_builder.py",
    "scripts/check_real_embedding_client_contract.py",
    "scripts/check_real_embedding_smoke.py",
    "scripts/probe_real_embedding_dimension.py",
    "scripts/check_embedding_config_gate.py",
    "scripts/create_quality_qdrant_collection.py",
    "scripts/upsert_quality_kb_chunks_to_postgres.py",
    "scripts/upsert_quality_kb_chunks_to_qdrant.py",
    "scripts/check_quality_kb_qdrant_retrieval.py",
    "scripts/check_quality_kb_retriever_adapter.py",
    "scripts/check_workflow_quality_kb_retrieval_integration.py",
    "scripts/check_quality_kb_grounded_e2e.py",
]


RUNTIME_CHECKS: Final[list[str]] = [
    "scripts/check_quality_questions_file.py",
    "scripts/check_quality_kb_chunk_builder.py",
    "scripts/check_real_embedding_client_contract.py",
    "scripts/probe_real_embedding_dimension.py",
    "scripts/check_embedding_config_gate.py",
    "scripts/create_quality_qdrant_collection.py",
    "scripts/upsert_quality_kb_chunks_to_postgres.py",
    "scripts/upsert_quality_kb_chunks_to_qdrant.py",
    "scripts/check_quality_kb_qdrant_retrieval.py",
    "scripts/check_quality_kb_retriever_adapter.py",
    "scripts/check_workflow_quality_kb_retrieval_integration.py",
    "scripts/check_quality_kb_grounded_e2e.py",
]


def run_command(
    *,
    title: str,
    args: list[str],
    env: dict[str, str],
) -> None:
    """Run one command and fail fast."""

    print("=" * 100)
    print(title)
    print(" ".join(args))

    completed = subprocess.run(
        args,
        cwd=BACKEND_ROOT,
        env=env,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{title} failed with exit code {completed.returncode}"
        )


def build_env() -> dict[str, str]:
    """Build regression env."""

    env = os.environ.copy()

    env["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    env["EMBEDDING_ENABLE_REAL_API"] = "1"
    env["EMBEDDING_PROVIDER"] = "local"
    env["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    env["EMBEDDING_API_KEY"] = ""
    env["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    env["EMBEDDING_DIMENSION"] = "1024"
    env["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    env["EMBEDDING_MAX_RETRIES"] = "2"
    env["EMBEDDING_BATCH_SIZE"] = "8"
    env["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    env["QUALITY_KB_TOP_K"] = "5"

    return env


def main() -> int:
    """Run Phase 3-I-B total regression."""

    env = build_env()

    print("=" * 100)
    print("Phase 3-I-B Quality KB total regression started")
    print("quality collection: quality_kb_v1")
    print("embedding model: BAAI/bge-m3")
    print("embedding dimension: 1024")

    try:
        run_command(
            title="compileall",
            args=[sys.executable, "-m", "compileall", *STATIC_FILES],
            env=env,
        )

        run_command(
            title="ruff",
            args=[sys.executable, "-m", "ruff", "check", *STATIC_FILES],
            env=env,
        )

        run_command(
            title="mypy",
            args=[
                sys.executable,
                "-m",
                "mypy",
                "--explicit-package-bases",
                *STATIC_FILES,
            ],
            env=env,
        )

        for script in RUNTIME_CHECKS:
            run_command(
                title=f"runtime check: {script}",
                args=[sys.executable, script],
                env=env,
            )

    except Exception as exc:
        print("=" * 100)
        print(f"Phase 3-I-B Quality KB total regression failed: {exc}")
        return 1

    print("=" * 100)
    print("Phase 3-I-B Quality KB total regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())