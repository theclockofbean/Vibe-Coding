"""Phase 3-G total regression check.

This script verifies Phase 3-F baseline plus Phase 3-G LLMClient integration.

It does not call real LLM APIs, generate business commitments, write API keys,
or let LLM output become final_response.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RegressionCheck:
    """One regression check command."""

    name: str
    command: list[str]
    env_overrides: dict[str, str] = field(default_factory=dict)


CHECKS: Final[tuple[RegressionCheck, ...]] = (
    RegressionCheck(
        name="phase3f_total_regression_with_llm_disabled",
        command=[sys.executable, "scripts/check_phase3f_total_regression.py"],
        env_overrides={
            "AGENT_LLM_NODE_ENABLED": "0",
            "AGENT_LLM_FORCE_ERROR": "0",
        },
    ),
    RegressionCheck(
        name="llm_client_contract",
        command=[sys.executable, "scripts/check_llm_client_contract.py"],
    ),
    RegressionCheck(
        name="rule_based_llm_client",
        command=[sys.executable, "scripts/check_rule_based_llm_client.py"],
    ),
    RegressionCheck(
        name="llm_safety_guard",
        command=[sys.executable, "scripts/check_llm_safety_guard.py"],
    ),
    RegressionCheck(
        name="workflow_llm_node",
        command=[sys.executable, "scripts/check_workflow_llm_node.py"],
        env_overrides={
            "AGENT_LLM_NODE_ENABLED": "1",
            "AGENT_LLM_FORCE_ERROR": "0",
        },
    ),
)


def run_check(
    check: RegressionCheck,
) -> bool:
    """Run one regression check."""

    print("=" * 80)
    print(f"running: {check.name}")
    print("command:", " ".join(check.command))

    env = os.environ.copy()
    env.update(check.env_overrides)

    completed = subprocess.run(
        check.command,
        cwd=BACKEND_ROOT,
        env=env,
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
    """Run Phase 3-G total regression."""

    print("phase3-g total regression started")
    print(f"backend root: {BACKEND_ROOT}")

    results: list[tuple[str, bool]] = []

    for check in CHECKS:
        passed = run_check(check)
        results.append((check.name, passed))

        if not passed:
            break

    print("=" * 80)
    print("phase3-g total regression summary")

    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"{status:<8} {name}")

    if not all(passed for _, passed in results):
        print("phase3-g total regression failed")
        return 1

    print("phase3-g total regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())