"""Inspect runtime contract of answer strategy helper."""

from __future__ import annotations

import inspect
from dataclasses import fields, is_dataclass
from pprint import pprint
from typing import Any

from app.agent.answering.multimodule_answer_strategy import (
    AnswerStrategyDecision,
    decide_answer_strategy,
)


def main() -> int:
    """Inspect contract."""

    print("=" * 80)
    print("inspecting Phase 3-I-I answer strategy runtime contract")

    result: dict[str, Any] = {
        "decide_answer_strategy_signature": str(
            inspect.signature(decide_answer_strategy)
        ),
        "answer_strategy_decision_is_dataclass": is_dataclass(
            AnswerStrategyDecision
        ),
        "answer_strategy_decision_fields": [],
        "answer_strategy_decision_methods": [],
    }

    if is_dataclass(AnswerStrategyDecision):
        result["answer_strategy_decision_fields"] = [
            {
                "name": field.name,
                "type": str(field.type),
                "default": str(field.default),
            }
            for field in fields(AnswerStrategyDecision)
        ]

    result["answer_strategy_decision_methods"] = [
        name
        for name in dir(AnswerStrategyDecision)
        if not name.startswith("_")
    ]

    pprint(result)

    print("Phase 3-I-I answer strategy runtime contract inspection passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())