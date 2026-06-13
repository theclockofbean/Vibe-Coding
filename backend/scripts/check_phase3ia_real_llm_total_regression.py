# ruff: noqa: E402,I001
"""Phase 3-I-A real LLM total regression.

This regression verifies:
- Phase 3-H compatibility under non-real-API mode;
- OpenAI-compatible client contract;
- real API smoke when configured;
- workflow LLM factory integration;
- LLM intent classifier fallback;
- workflow intent fallback;
- quality real LLM rendering.

API keys are never printed.
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
class RegressionStep:
    """One regression step."""

    name: str
    script: str
    env_overrides: dict[str, str] = field(default_factory=dict)


LEGACY_SAFE_ENV: Final[dict[str, str]] = {
    "AGENT_LLM_NODE_ENABLED": "1",
    "AGENT_LLM_FORCE_ERROR": "0",
    "AGENT_RENDER_FORCE_ERROR": "0",
    "LLM_INTENT_CLASSIFIER_ENABLED": "0",
    "LLM_ENABLE_REAL_API": "0",
    "LLM_PROVIDER": "rule_based",
    "LLM_BASE_URL": "",
    "LLM_API_KEY": "",
    "LLM_MODEL": "",
}


REAL_LLM_SAFE_ENV: Final[dict[str, str]] = {
    "AGENT_LLM_NODE_ENABLED": "1",
    "AGENT_LLM_FORCE_ERROR": "0",
    "AGENT_RENDER_FORCE_ERROR": "0",
    "LLM_INTENT_CLASSIFIER_ENABLED": "1",
}


REGRESSION_STEPS: Final[tuple[RegressionStep, ...]] = (
    RegressionStep(
        name="phase3h_legacy_total_regression_without_real_api",
        script="scripts/check_phase3h_total_regression.py",
        env_overrides=LEGACY_SAFE_ENV,
    ),
    RegressionStep(
        name="openai_compatible_llm_client_contract",
        script="scripts/check_openai_compatible_llm_client_contract.py",
    ),
    RegressionStep(
        name="real_llm_api_smoke",
        script="scripts/check_real_llm_api_smoke.py",
    ),
    RegressionStep(
        name="workflow_llm_factory_integration",
        script="scripts/check_workflow_llm_factory_integration.py",
        env_overrides=REAL_LLM_SAFE_ENV,
    ),
    RegressionStep(
        name="llm_intent_classifier_fallback",
        script="scripts/check_llm_intent_classifier_fallback.py",
        env_overrides=REAL_LLM_SAFE_ENV,
    ),
    RegressionStep(
        name="workflow_llm_intent_fallback",
        script="scripts/check_workflow_llm_intent_fallback.py",
        env_overrides=REAL_LLM_SAFE_ENV,
    ),
    RegressionStep(
        name="quality_real_llm_rendering",
        script="scripts/check_quality_real_llm_rendering.py",
        env_overrides=REAL_LLM_SAFE_ENV,
    ),
)


def run_step(
    step: RegressionStep,
) -> bool:
    """Run one regression step."""

    script_path = BACKEND_ROOT / step.script

    if not script_path.exists():
        print(f"FAILED {step.name}: script not found: {step.script}")
        return False

    env = os.environ.copy()
    env.update(step.env_overrides)

    print("=" * 80)
    print(f"running {step.name}")
    print(
        {
            "script": step.script,
            "real_api_enabled": _env_bool(env.get("LLM_ENABLE_REAL_API", "")),
            "provider": env.get("LLM_PROVIDER", ""),
            "base_url_configured": bool(env.get("LLM_BASE_URL", "")),
            "api_key_configured": bool(env.get("LLM_API_KEY", "")),
            "model": env.get("LLM_MODEL", ""),
            "intent_classifier_enabled": env.get(
                "LLM_INTENT_CLASSIFIER_ENABLED",
                "",
            ),
        }
    )

    completed = subprocess.run(
        [sys.executable, step.script],
        cwd=BACKEND_ROOT,
        env=env,
        check=False,
    )

    if completed.returncode != 0:
        print(f"FAILED {step.name}: exit_code={completed.returncode}")
        return False

    print(f"PASSED {step.name}")
    return True


def _env_bool(
    value: str,
) -> bool:
    """Return bool from env string."""

    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    """Run Phase 3-I-A total regression."""

    print("=" * 80)
    print("Phase 3-I-A real LLM total regression")
    print(f"backend_root={BACKEND_ROOT}")

    results: list[tuple[str, bool]] = []

    for step in REGRESSION_STEPS:
        passed = run_step(step)
        results.append((step.name, passed))

    print("=" * 80)
    print("Phase 3-I-A regression summary")

    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"{status:<8} {name}")

    if not all(passed for _, passed in results):
        print("Phase 3-I-A real LLM total regression failed")
        return 1

    print("Phase 3-I-A real LLM total regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())