# ruff: noqa: E402,I001
"""Check Answer Strategy risk handoff gate after noise reduction."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.answering.multimodule_answer_strategy import decide_answer_strategy
from app.agent.answering.multimodule_answer_strategy import load_answer_strategy_config


RISK_HANDOFF_CASES: Final[tuple[dict[str, object], ...]] = (
    {
        "query": "SKU003真皮那款有锥度要求吗 怎么安装",
        "selected_module": "spec",
        "candidate_modules": ["spec"],
    },
    {
        "query": "SKU011适配宝马那款 螺纹和锥度是多少",
        "selected_module": "spec",
        "candidate_modules": ["spec"],
    },
    {
        "query": "发顺丰去新疆多少差价",
        "selected_module": "logistics",
        "candidate_modules": ["logistics"],
    },
    {
        "query": "需要1000个SKU020 报个价",
        "selected_module": "price",
        "candidate_modules": ["price"],
    },
    {
        "query": "我老客户了 给我个实在价",
        "selected_module": None,
        "candidate_modules": [],
    },
    {
        "query": "你们的是原厂件吗",
        "selected_module": None,
        "candidate_modules": [],
    },
    {
        "query": "你们是骗子 东西根本用不了 我要差评投诉",
        "selected_module": None,
        "candidate_modules": [],
    },
    {
        "query": "我想定制一批带我们公司LOGO的球头 500个",
        "selected_module": None,
        "candidate_modules": [],
    },
)

NORMAL_CASES: Final[tuple[dict[str, object], ...]] = (
    {
        "query": "SKU001螺纹规格是多少",
        "selected_module": "spec",
        "candidate_modules": ["spec"],
    },
    {
        "query": "SKU030钛合金竞技球头 有锥度吗 什么材质",
        "selected_module": "spec",
        "candidate_modules": ["spec"],
    },
    {
        "query": "SKU050黄铜锥形球头 锥度是多少 螺纹呢",
        "selected_module": "spec",
        "candidate_modules": ["spec"],
    },
    {
        "query": "SKU058不锈钢锥形球头 锥度和螺纹",
        "selected_module": "spec",
        "candidate_modules": ["spec"],
    },
)


def main() -> int:
    """Run v2 answer strategy risk gate check."""

    print("=" * 80)
    print("checking Phase 3-I-I answer strategy risk gate v2")

    config = load_answer_strategy_config()
    errors: list[str] = []
    results: list[dict[str, Any]] = []

    for case in RISK_HANDOFF_CASES:
        result = evaluate_case(case=case, config=config)
        results.append(result)

        if result["strategy_mode"] != "handoff_required":
            errors.append(f"risk case expected handoff_required, got {result}")

        if result["handoff_required"] is not True:
            errors.append(f"risk case did not require handoff: {result}")

    for case in NORMAL_CASES:
        result = evaluate_case(case=case, config=config)
        results.append(result)

        if result["strategy_mode"] != "single_primary":
            errors.append(f"normal case expected single_primary, got {result}")

        if result["handoff_required"] is True:
            errors.append(f"normal case should not require handoff: {result}")

    pprint({"results": results, "errors": errors})

    if errors:
        print("Phase 3-I-I answer strategy risk gate v2 check failed")
        return 1

    print("Phase 3-I-I answer strategy risk gate v2 check passed")
    return 0


def evaluate_case(
    *,
    case: dict[str, object],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one case."""

    query = str(case["query"])
    selected_module_value = case["selected_module"]
    selected_module = (
        str(selected_module_value)
        if selected_module_value is not None
        else None
    )
    candidate_modules = as_str_list(case["candidate_modules"])

    decision = decide_answer_strategy(
        query=query,
        selected_module=selected_module,
        candidate_modules=candidate_modules,
        conflict_type=None,
        strategy_config=config,
    )

    return {
        "query": query,
        "selected_module": selected_module,
        "candidate_modules": candidate_modules,
        "strategy_mode": decision.strategy_mode,
        "handoff_required": decision.handoff_required,
        "safety_blocked": decision.safety_blocked,
        "reason": decision.reason,
    }


def as_str_list(value: object) -> list[str]:
    """Convert object to list[str]."""

    if isinstance(value, list):
        return [str(item) for item in value]

    if isinstance(value, tuple):
        return [str(item) for item in value]

    return [str(value)]


if __name__ == "__main__":
    raise SystemExit(main())