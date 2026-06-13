"""Run Phase 3-I-F total regression."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from pprint import pprint
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

CHECK_SCRIPTS: Final[tuple[str, ...]] = (
    "scripts/check_phase3if_four_kb_baseline.py",
    "scripts/check_phase3if_routing_design_doc.py",
    "scripts/check_phase3if_conflict_cases_doc.py",
    "scripts/check_phase3if_conflict_cases_json.py",
    "scripts/check_phase3if_unified_kb_router.py",
    "scripts/check_phase3if_workflow_unified_router_integration.py",
    "scripts/check_phase3if_conflict_workflow_e2e.py",
    "scripts/check_phase3ie_spec_kb_total_regression.py",
    "scripts/check_phase3id_price_kb_total_regression.py",
    "scripts/check_phase3ic_logistics_kb_total_regression.py",
)


def main() -> int:
    """Run total regression."""

    print("=" * 80)
    print("running Phase 3-I-F total regression")

    set_required_env()

    errors: list[str] = []
    results: list[dict[str, object]] = []

    for script in CHECK_SCRIPTS:
        result = run_script(script=script)
        results.append(result)

        if result["returncode"] != 0:
            errors.append(script)

    summary = {
        "script_count": len(CHECK_SCRIPTS),
        "failed_scripts": errors,
        "results": results,
    }

    pprint(summary)

    if errors:
        print("Phase 3-I-F total regression failed")
        return 1

    print("Phase 3-I-F total regression passed")
    return 0


def set_required_env() -> None:
    """Set env vars for real KB checks."""

    os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")

    os.environ["QUALITY_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["LOGISTICS_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["PRICE_KB_RETRIEVER_ENABLED"] = "1"
    os.environ["SPEC_KB_RETRIEVER_ENABLED"] = "1"

    os.environ["QDRANT_COLLECTION_QUALITY"] = "quality_kb_v1"
    os.environ["QDRANT_COLLECTION_LOGISTICS"] = "logistics_kb_v1"
    os.environ["QDRANT_COLLECTION_PRICE"] = "price_kb_v1"
    os.environ["QDRANT_COLLECTION_SPEC"] = "spec_kb_v1"

    os.environ["QUALITY_KB_COLLECTION_NAME"] = "quality_kb_v1"
    os.environ["LOGISTICS_KB_COLLECTION_NAME"] = "logistics_kb_v1"
    os.environ["PRICE_KB_COLLECTION_NAME"] = "price_kb_v1"
    os.environ["SPEC_KB_COLLECTION_NAME"] = "spec_kb_v1"

    os.environ["QUALITY_KB_TOP_K"] = "5"
    os.environ["LOGISTICS_KB_TOP_K"] = "5"
    os.environ["PRICE_KB_TOP_K"] = "5"
    os.environ["SPEC_KB_TOP_K"] = "5"

    os.environ["EMBEDDING_ENABLE_REAL_API"] = "1"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_BASE_URL"] = "http://127.0.0.1:8088"
    os.environ["EMBEDDING_API_KEY"] = ""
    os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    os.environ["EMBEDDING_DIMENSION"] = "1024"
    os.environ["EMBEDDING_TIMEOUT_SECONDS"] = "240"
    os.environ["EMBEDDING_BATCH_SIZE"] = "1"


def run_script(
    *,
    script: str,
) -> dict[str, object]:
    """Run one check script."""

    print("-" * 80)
    print(f"running {script}")

    completed = subprocess.run(  # noqa: S603
        [sys.executable, script],
        cwd=BACKEND_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    if completed.stdout:
        print(completed.stdout)

    if completed.stderr:
        print(completed.stderr, file=sys.stderr)

    return {
        "script": script,
        "returncode": completed.returncode,
    }


if __name__ == "__main__":
    raise SystemExit(main())