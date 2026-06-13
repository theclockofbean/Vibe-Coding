"""Run Phase 3-I-C Logistics KB total regression checks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

CHECK_COMMANDS: Final[tuple[tuple[str, ...], ...]] = (
    ("python", "scripts/check_logistics_questions_file.py"),
    ("python", "scripts/check_logistics_kb_chunk_builder.py"),
    ("python", "scripts/check_logistics_kb_qdrant_retrieval.py"),
    ("python", "scripts/check_logistics_kb_retriever_adapter.py"),
    ("python", "scripts/check_workflow_logistics_kb_retrieval_integration.py"),
    ("python", "scripts/check_logistics_kb_grounded_e2e.py"),
    ("python", "scripts/check_phase3ib_quality_kb_total_regression.py"),
)


def main() -> int:
    """Run total regression."""

    set_required_env()

    print("=" * 80)
    print("Phase 3-I-C Logistics KB total regression started")

    failed_commands: list[str] = []

    for command in CHECK_COMMANDS:
        command_display = " ".join(command)
        script_path = BACKEND_ROOT / command[1]

        if not script_path.exists():
            print("-" * 80)
            print(f"SKIP missing script: {command_display}")
            continue

        print("-" * 80)
        print(f"RUN {command_display}")

        completed = subprocess.run(  # noqa: S603
            command,
            cwd=BACKEND_ROOT,
            check=False,
        )

        if completed.returncode != 0:
            failed_commands.append(command_display)
            print(f"FAILED {command_display}")
        else:
            print(f"PASSED {command_display}")

    print("=" * 80)

    if failed_commands:
        print("Phase 3-I-C Logistics KB total regression failed")
        for command_display in failed_commands:
            print(f"- {command_display}")
        return 1

    print("Phase 3-I-C Logistics KB total regression passed")
    return 0


def set_required_env() -> None:
    """Set required env vars for real Logistics and Quality KB checks."""

    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["LOGISTICS_KB_TOP_K"] = "5"

    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    os.environ["QUALITY_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "120"
    os.environ["EMBEDDING_MAX_RETRIES"] = "2"
    os.environ["EMBEDDING_BATCH_SIZE"] = "8"


if __name__ == "__main__":
    raise SystemExit(main())