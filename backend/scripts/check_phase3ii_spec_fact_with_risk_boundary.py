"""Check spec facts can answer with risk boundary."""

from __future__ import annotations

from pprint import pprint
from typing import Final, NamedTuple

from app.agent.answering.multimodule_answer_strategy import decide_answer_strategy


class TargetCase(NamedTuple):
    """Target case definition."""

    case_id: str
    query: str
    selected_module: str | None
    candidate_modules: tuple[str, ...]
    expected_strategy_mode: str
    expected_handoff_required: bool


TARGET_CASES: Final[tuple[TargetCase, ...]] = (
    TargetCase(
        case_id="TC_SPEC_003",
        query="SKU003真皮那款有锥度要求吗 怎么安装",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="primary_with_boundary_note",
        expected_handoff_required=False,
    ),
    TargetCase(
        case_id="TC_SPEC_006",
        query="SKU011适配宝马那款 螺纹和锥度是多少",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="primary_with_boundary_note",
        expected_handoff_required=False,
    ),
    TargetCase(
        case_id="TC_SPEC_013",
        query="SKU064带温控加热的球头 螺纹是多少 USB接口怎么用",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="primary_with_boundary_note",
        expected_handoff_required=False,
    ),
    TargetCase(
        case_id="TC_SPEC_019",
        query="SKU022铝合金梯形球头 有锥度要求吗",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="single_primary",
        expected_handoff_required=False,
    ),
    TargetCase(
        case_id="TC_SPEC_021",
        query="你们有没有M14螺纹的球头",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="handoff_required",
        expected_handoff_required=True,
    ),
)


def main() -> int:
    """Run targeted checks."""

    print("=" * 80)
    print("checking Phase 3-I-I spec fact with risk boundary")

    errors: list[str] = []
    rows: list[dict[str, object]] = []

    for case in TARGET_CASES:
        decision = decide_answer_strategy(
            query=case.query,
            selected_module=case.selected_module,
            candidate_modules=list(case.candidate_modules),
            conflict_type=None,
            strategy_config=None,
        )

        row = {
            "case_id": case.case_id,
            "query": case.query,
            "expected_strategy_mode": case.expected_strategy_mode,
            "actual_strategy_mode": decision.strategy_mode,
            "expected_handoff_required": case.expected_handoff_required,
            "actual_handoff_required": decision.handoff_required,
            "split_required": decision.split_required,
            "safety_blocked": decision.safety_blocked,
            "boundary_note_type": decision.boundary_note_type,
            "boundary_notes": decision.boundary_notes,
            "reason": decision.reason,
        }

        rows.append(row)

        if decision.strategy_mode != case.expected_strategy_mode:
            errors.append(
                f"{case.case_id}: expected mode {case.expected_strategy_mode}, "
                f"got {decision.strategy_mode}"
            )

        if decision.handoff_required != case.expected_handoff_required:
            errors.append(
                f"{case.case_id}: expected handoff_required "
                f"{case.expected_handoff_required}, got {decision.handoff_required}"
            )

        if decision.safety_blocked:
            errors.append(f"{case.case_id}: should not be safety_blocked")

    pprint({"rows": rows, "errors": errors})

    if errors:
        print("Phase 3-I-I spec fact with risk boundary check failed")
        return 1

    print("Phase 3-I-I spec fact with risk boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())