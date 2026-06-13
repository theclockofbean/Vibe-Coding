"""Run Phase 3-I-E Spec KB total regression."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

CHECK_SCRIPTS: Final[tuple[str, ...]] = (
    "scripts/check_spec_questions_file.py",
    "scripts/check_spec_kb_chunk_builder.py",
    "scripts/check_spec_kb_qdrant_retrieval.py",
    "scripts/check_spec_kb_retriever_adapter.py",
    "scripts/check_workflow_spec_kb_retrieval_integration.py",
    "scripts/check_spec_kb_grounded_e2e.py",
    "scripts/check_phase3id_price_kb_total_regression.py",
    "scripts/check_phase3ic_logistics_kb_total_regression.py",
)


def main() -> int:
    """Run total regression."""

    print("=" * 80)
    print("running Phase 3-I-E Spec KB total regression")

    set_required_env()

    missing_scripts = [
        script
        for script in CHECK_SCRIPTS
        if not (BACKEND_ROOT / script).exists()
    ]

    if missing_scripts:
        pprint(
            {
                "error": "missing regression scripts",
                "missing_scripts": missing_scripts,
            }
        )
        return 1

    results: list[dict[str, object]] = []
    failed: list[str] = []

    for script in CHECK_SCRIPTS:
        print("\n" + "=" * 80)
        print(f"running {script}")

        completed = subprocess.run(  # noqa: S603
            [sys.executable, script],
            cwd=BACKEND_ROOT,
            check=False,
        )

        result = {
            "script": script,
            "returncode": completed.returncode,
            "passed": completed.returncode == 0,
        }
        results.append(result)

        if completed.returncode != 0:
            failed.append(script)

    summary = {
        "script_count": len(CHECK_SCRIPTS),
        "passed_count": len(CHECK_SCRIPTS) - len(failed),
        "failed_count": len(failed),
        "failed_scripts": failed,
        "results": results,
    }

    pprint(summary)

    if failed:
        print("Phase 3-I-E Spec KB total regression failed")
        return 1

    print("Phase 3-I-E Spec KB total regression passed")
    return 0


def set_required_env() -> None:
    """Set required env vars for all KB modules."""

    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_SPEC"] = "spec_kb_v1"
    os.environ["SPEC_KB_COLLECTION_NAME"] = "spec_kb_v1"
    os.environ["SPEC_KB_TOP_K"] = "5"

    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_PRICE"] = "price_kb_v1"
    os.environ["PRICE_KB_COLLECTION_NAME"] = "price_kb_v1"
    os.environ["PRICE_KB_TOP_K"] = "5"

    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["LOGISTICS_KB_COLLECTION_NAME"] = "logistics_kb_v1"
    os.environ["LOGISTICS_KB_TOP_K"] = "5"

    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    os.environ["QUALITY_KB_COLLECTION_NAME"] = "quality_kb_v1"
    os.environ["QUALITY_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "240"
    os.environ["EMBEDDING_BATCH_SIZE"] = "1"


if __name__ == "__main__":
    raise SystemExit(main())