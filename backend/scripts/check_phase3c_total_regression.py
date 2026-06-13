"""Run Phase 3-C total regression checks.

This script runs Phase 3-B total regression plus AgentState contract checks.

It does not call an LLM, generate customer-facing answers, promise prices,
promise logistics, promise quality, promise warranty, promise returns/exchanges,
promise compensation, or write business commitments.
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
        name="phase3b_total_regression",
        relative_path="check_phase3b_total_regression.py",
    ),
    RegressionScript(
        name="agent_state_contract",
        relative_path="check_agent_state_contract.py",
    ),
    RegressionScript(
        name="agent_state_unified_api_compatibility",
        relative_path="check_agent_state_unified_api_compatibility.py",
    ),
)


def validate_scripts_exist() -> bool:
    """Check all regression scripts exist before running."""

    print("=" * 100)
    print("validating regression scripts")

    missing_scripts: list[Path] = []

    for script in REGRESSION_SCRIPTS:
        script_path = SCRIPTS_ROOT / script.relative_path

        if not script_path.exists():
            missing_scripts.append(script_path)

    if missing_scripts:
        print("failed: missing regression scripts")

        for script_path in missing_scripts:
            print(f"- {script_path}")

        return False

    print("all regression scripts exist")
    return True


def run_regression_script(script: RegressionScript) -> RegressionResult:
    """Run one regression script."""

    script_path = SCRIPTS_ROOT / script.relative_path

    print("=" * 100)
    print(f"running: {script.name}")
    print(f"script: {script_path}")

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
    print("phase3-c total regression summary")

    for result in results:
        status = "PASSED" if result.passed else "FAILED"
        print(
            f"{status:<8} {result.name:<48} "
            f"return_code={result.return_code:<3} "
            f"elapsed_seconds={result.elapsed_seconds:.2f}"
        )


def main() -> int:
    """Run all Phase 3-C total regression scripts."""

    print("=" * 100)
    print("starting phase3-c total regression")
    print(f"backend_root: {BACKEND_ROOT}")
    print(f"python: {sys.executable}")

    if not validate_scripts_exist():
        print("phase3-c total regression failed")
        return 1

    results = [
        run_regression_script(script)
        for script in REGRESSION_SCRIPTS
    ]

    print_summary(results)

    if not all(result.passed for result in results):
        print("phase3-c total regression failed")
        return 1

    print("phase3-c total regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())