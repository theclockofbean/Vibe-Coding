"""Run Phase 3-I-D Price KB total regression checks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

CHECK_SCRIPTS: Final[tuple[str, ...]] = (
    "scripts/check_price_questions_file.py",
    "scripts/check_price_kb_chunk_builder.py",
    "scripts/check_price_kb_qdrant_retrieval.py",
    "scripts/check_price_kb_retriever_adapter.py",
    "scripts/check_workflow_price_kb_retrieval_integration.py",
    "scripts/check_price_kb_grounded_e2e.py",
    "scripts/check_phase3ic_logistics_kb_total_regression.py",
)


def main() -> int:
    """Run total regression."""

    set_required_env()

    print("=" * 80)
    print("Phase 3-I-D Price KB total regression started")

    failed_scripts: list[str] = []
    skipped_scripts: list[str] = []

    for script in CHECK_SCRIPTS:
        script_path = BACKEND_ROOT / script

        print("-" * 80)

        if not script_path.exists():
            print(f"SKIP missing script: {script}")
            skipped_scripts.append(script)
            continue

        print(f"RUN {script}")

        completed = subprocess.run(  # noqa: S603
            [sys.executable, script],
            cwd=BACKEND_ROOT,
            check=False,
        )

        if completed.returncode != 0:
            failed_scripts.append(script)
            print(f"FAILED {script}")
        else:
            print(f"PASSED {script}")

    print("=" * 80)

    if skipped_scripts:
        print("Skipped scripts:")
        for script in skipped_scripts:
            print(f"- {script}")

    if failed_scripts:
        print("Phase 3-I-D Price KB total regression failed")
        for script in failed_scripts:
            print(f"- {script}")
        return 1

    print("Phase 3-I-D Price KB total regression passed")
    return 0


def set_required_env() -> None:
    """Set required env vars for real Price, Logistics and Quality KB checks."""

    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_PRICE"] = "price_kb_v1"
    os.environ["PRICE_KB_TOP_K"] = "5"

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