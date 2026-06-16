"""Run all archived backend regression gates in order."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RegressionScript:
    """A regression gate script."""

    name: str
    path: Path
    requires_external_services: bool = False
    requires_real_llm: bool = False


REGRESSION_SCRIPTS: Final[tuple[RegressionScript, ...]] = (
    RegressionScript("phase2", BACKEND_ROOT / "scripts/check_phase2_total_regression.py"),
    RegressionScript("phase3a", BACKEND_ROOT / "scripts/check_phase3a_total_regression.py"),
    RegressionScript("phase3b", BACKEND_ROOT / "scripts/check_phase3b_total_regression.py"),
    RegressionScript("phase3c", BACKEND_ROOT / "scripts/check_phase3c_total_regression.py"),
    RegressionScript("phase3d", BACKEND_ROOT / "scripts/check_phase3d_total_regression.py"),
    RegressionScript("phase3e", BACKEND_ROOT / "scripts/check_phase3e_total_regression.py"),
    RegressionScript(
        "phase3f",
        BACKEND_ROOT / "scripts/check_phase3f_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript("phase3g", BACKEND_ROOT / "scripts/check_phase3g_total_regression.py"),
    RegressionScript("phase3h", BACKEND_ROOT / "scripts/check_phase3h_total_regression.py"),
    RegressionScript(
        "phase3ia",
        BACKEND_ROOT / "scripts/check_phase3ia_real_llm_total_regression.py",
        requires_real_llm=True,
    ),
    RegressionScript(
        "phase3ib",
        BACKEND_ROOT / "scripts/check_phase3ib_quality_kb_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript(
        "phase3ic",
        BACKEND_ROOT / "scripts/check_phase3ic_logistics_kb_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript(
        "phase3id",
        BACKEND_ROOT / "scripts/check_phase3id_price_kb_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript(
        "phase3ie",
        BACKEND_ROOT / "scripts/check_phase3ie_spec_kb_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript(
        "phase3if",
        BACKEND_ROOT / "scripts/check_phase3if_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript(
        "phase3ig",
        BACKEND_ROOT / "scripts/check_phase3ig_renderer_gate_total_regression.py",
        requires_external_services=True,
    ),
    RegressionScript(
        "phase3ih",
        BACKEND_ROOT / "scripts/check_phase3ih_frontend_payload_total_regression.py",
        requires_external_services=True,
    ),
)

REAL_LLM_50_CASE_SCRIPT: Final[RegressionScript] = RegressionScript(
    "phase3ii_50_case",
    BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py",
    requires_external_services=True,
    requires_real_llm=True,
)


def main() -> int:
    """Run regression scripts."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="Include gates that require live Qdrant/embedding services.",
    )
    parser.add_argument(
        "--include-real-llm",
        action="store_true",
        help="Include gates that require real LLM credentials.",
    )
    parser.add_argument(
        "--include-50-case",
        action="store_true",
        help="Include Phase 3-I-I real LLM 50-case evaluation.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue after failures and summarize all failures.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List selected scripts without running them.",
    )
    args = parser.parse_args()

    selected = select_scripts(
        include_external=bool(args.include_external),
        include_real_llm=bool(args.include_real_llm),
        include_50_case=bool(args.include_50_case),
    )

    if args.list:
        for script in selected:
            print(script.path.relative_to(BACKEND_ROOT))
        return 0

    failures: list[tuple[str, int]] = []
    started_at = time.perf_counter()

    print("=" * 80)
    print("running backend regression suite")
    print(f"backend_root={BACKEND_ROOT}")
    print(f"script_count={len(selected)}")

    for index, script in enumerate(selected, start=1):
        print("-" * 80)
        print(f"[{index}/{len(selected)}] {script.name}: {script.path.name}")

        if not script.path.exists():
            print(f"missing script: {script.path}")
            failures.append((script.name, 127))
            if not args.keep_going:
                break
            continue

        code = run_script(script)
        if code != 0:
            failures.append((script.name, code))
            print(f"FAILED {script.name}: exit_code={code}")
            if not args.keep_going:
                break

    elapsed = round(time.perf_counter() - started_at, 2)
    print("=" * 80)
    print(f"regression suite completed in {elapsed}s")

    if failures:
        print("failures:")
        for name, code in failures:
            print(f"- {name}: {code}")
        return 1

    print("all selected regression gates passed")
    return 0


def select_scripts(
    *,
    include_external: bool,
    include_real_llm: bool,
    include_50_case: bool,
) -> list[RegressionScript]:
    """Return scripts selected by capability flags."""

    scripts: list[RegressionScript] = []

    for script in REGRESSION_SCRIPTS:
        if script.requires_external_services and not include_external:
            continue

        if script.requires_real_llm and not include_real_llm:
            continue

        scripts.append(script)

    if include_50_case:
        if REAL_LLM_50_CASE_SCRIPT.requires_external_services and not include_external:
            print("--include-50-case requires --include-external")
        elif REAL_LLM_50_CASE_SCRIPT.requires_real_llm and not include_real_llm:
            print("--include-50-case requires --include-real-llm")
        else:
            scripts.append(REAL_LLM_50_CASE_SCRIPT)

    return scripts


def run_script(script: RegressionScript) -> int:
    """Run one script in a subprocess."""

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_ROOT)

    completed = subprocess.run(
        [sys.executable, str(script.path)],
        cwd=BACKEND_ROOT,
        env=env,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
