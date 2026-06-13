"""Run Phase 2 total regression checks.

This script runs all Phase 1 and Phase 2 local regression scripts in sequence.

It does not call an LLM, generate customer-facing answers, promise prices,
promise logistics, promise quality, promise warranty, promise returns/exchanges,
promise compensation, or write data.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT: Final[Path] = BACKEND_ROOT / "scripts"


@dataclass(frozen=True)
class RegressionScript:
    """One regression script entry."""

    name: str
    relative_path: str


@dataclass(frozen=True)
class RegressionResult:
    """One regression script execution result."""

    name: str
    script_path: Path
    return_code: int
    elapsed_seconds: float

    @property
    def passed(self) -> bool:
        """Whether the regression script passed."""

        return self.return_code == 0


REGRESSION_SCRIPTS: Final[tuple[RegressionScript, ...]] = (
    RegressionScript(
        name="phase1_api_routes",
        relative_path="check_phase1_api_routes.py",
    ),
    RegressionScript(
        name="unified_intent_router",
        relative_path="check_unified_intent_router.py",
    ),
    RegressionScript(
        name="unified_text_qa_service",
        relative_path="check_unified_text_qa_service.py",
    ),
    RegressionScript(
        name="unified_agent_api",
        relative_path="check_unified_agent_api.py",
    ),
    RegressionScript(
        name="unified_agent_api_boundaries",
        relative_path="check_unified_agent_api_boundaries.py",
    ),
)


def run_regression_script(script: RegressionScript) -> RegressionResult:
    """Run one regression script."""

    script_path = SCRIPTS_ROOT / script.relative_path

    print("=" * 100)
    print(f"running: {script.name}")
    print(f"script: {script_path}")

    if not script_path.exists():
        print(f"failed: script does not exist: {script_path}")
        return RegressionResult(
            name=script.name,
            script_path=script_path,
            return_code=1,
            elapsed_seconds=0.0,
        )

    started_at = time.perf_counter()

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BACKEND_ROOT,
        check=False,
    )

    elapsed_seconds = time.perf_counter() - started_at

    print("-" * 100)
    print(
        f"finished: {script.name} "
        f"return_code={completed.returncode} "
        f"elapsed_seconds={elapsed_seconds:.2f}"
    )

    return RegressionResult(
        name=script.name,
        script_path=script_path,
        return_code=completed.returncode,
        elapsed_seconds=elapsed_seconds,
    )


def print_summary(results: list[RegressionResult]) -> None:
    """Print total regression summary."""

    print("=" * 100)
    print("phase2 total regression summary")

    for result in results:
        status = "PASSED" if result.passed else "FAILED"
        print(
            f"{status:<8} {result.name:<35} "
            f"return_code={result.return_code:<3} "
            f"elapsed_seconds={result.elapsed_seconds:.2f}"
        )


def main() -> int:
    """Run all Phase 2 total regression scripts."""

    print("=" * 100)
    print("starting phase2 total regression")
    print(f"backend_root: {BACKEND_ROOT}")
    print(f"python: {sys.executable}")

    results = [
        run_regression_script(script)
        for script in REGRESSION_SCRIPTS
    ]

    print_summary(results)

    if not all(result.passed for result in results):
        print("phase2 total regression failed")
        return 1

    print("phase2 total regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())