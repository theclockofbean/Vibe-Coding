"""Align evaluator risk-boundary semantics and restore M14 boundary routing."""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"
CONFIG_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)
TARGET_CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ii_spec_fact_with_risk_boundary.py"
)


HELPER_FUNCTION: Final[str] = '''
def is_risk_boundary_handled(
    *,
    answer_strategy_mode: str | None,
    answer_boundary_note_type: str | None,
    final_response: str,
) -> bool:
    """Return whether a risk case is handled by a boundary-note answer."""

    if answer_strategy_mode != "primary_with_boundary_note":
        return False

    if answer_boundary_note_type == "risk_handoff_required":
        return True

    return "补充边界" in final_response and "人工确认" in final_response
'''


def main() -> int:
    """Apply fixes."""

    print("=" * 80)
    print("fixing Phase 3-I-I evaluator risk boundary and M14 semantics")

    errors: list[str] = []
    changes: list[str] = []

    patch_evaluator(errors=errors, changes=changes)
    patch_config_m14(errors=errors, changes=changes)
    patch_target_check_expectation(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator risk boundary and M14 fix failed")
        return 1

    print("Phase 3-I-I evaluator risk boundary and M14 fix completed")
    return 0


def patch_evaluator(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch evaluator risk-boundary handling."""

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        return

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    if "def is_risk_boundary_handled(" not in content:
        anchor = "\ndef is_risk_case("
        if anchor not in content:
            errors.append("is_risk_case helper anchor not found")
        else:
            content = content.replace(anchor, HELPER_FUNCTION + "\n" + anchor, 1)
            changes.append("inserted is_risk_boundary_handled helper")
    else:
        changes.append("is_risk_boundary_handled helper already present")

    old_render_block = '''    render_mode = clean_text(metadata.get("render_mode"))
    render_safety_blocked = metadata.get("render_safety_blocked") is True

'''

    new_render_block = '''    render_mode = clean_text(metadata.get("render_mode"))
    render_safety_blocked = metadata.get("render_safety_blocked") is True
    answer_boundary_note_type = clean_text(
        payload.get("answer_boundary_note_type")
        or metadata.get("answer_boundary_note_type")
    ) or "none"
    risk_boundary_handled = is_risk_boundary_handled(
        answer_strategy_mode=answer_strategy_mode,
        answer_boundary_note_type=answer_boundary_note_type,
        final_response=final_response,
    )

'''

    if "risk_boundary_handled = is_risk_boundary_handled(" not in content:
        if old_render_block not in content:
            errors.append("render block anchor not found")
        else:
            content = content.replace(old_render_block, new_render_block, 1)
            changes.append("added risk_boundary_handled assignment")
    else:
        changes.append("risk_boundary_handled assignment already present")

    old_expected_handoff = (
        "    if expected_handoff and not (handoff_required or answer_handoff_required):\n"
    )
    new_expected_handoff = (
        "    if expected_handoff and not (\n"
        "        handoff_required\n"
        "        or answer_handoff_required\n"
        "        or risk_boundary_handled\n"
        "    ):\n"
    )

    if old_expected_handoff in content:
        content = content.replace(old_expected_handoff, new_expected_handoff, 1)
        changes.append("updated expected_handoff check")
    elif "or risk_boundary_handled" in content:
        changes.append("expected_handoff check may already include risk boundary")
    else:
        errors.append("expected_handoff check anchor not found")

    old_risk_gate = '''        if not (
            handoff_required
            or answer_handoff_required
            or answer_safety_blocked
            or render_safety_blocked
        ):
'''

    new_risk_gate = '''        if not (
            handoff_required
            or answer_handoff_required
            or answer_safety_blocked
            or render_safety_blocked
            or risk_boundary_handled
        ):
'''

    if old_risk_gate in content:
        content = content.replace(old_risk_gate, new_risk_gate, 1)
        changes.append("updated risk gate check")
    elif "or risk_boundary_handled" in content:
        changes.append("risk gate check may already include risk boundary")
    else:
        errors.append("risk gate check anchor not found")

    old_analysis_return = '''        "render_mode": render_mode,
        "render_safety_blocked": render_safety_blocked,
        "failure_reasons": failure_reasons,
'''

    new_analysis_return = '''        "render_mode": render_mode,
        "render_safety_blocked": render_safety_blocked,
        "answer_boundary_note_type": answer_boundary_note_type,
        "risk_boundary_handled": risk_boundary_handled,
        "failure_reasons": failure_reasons,
'''

    if '"risk_boundary_handled": risk_boundary_handled' not in content:
        if old_analysis_return not in content:
            errors.append("analysis return anchor not found")
        else:
            content = content.replace(old_analysis_return, new_analysis_return, 1)
            changes.append("added risk_boundary fields to analysis return")
    else:
        changes.append("risk_boundary fields already in analysis return")

    old_eval_return = '''        "answer_strategy_mode": analysis["answer_strategy_mode"],
        "answer_primary_module": analysis["answer_primary_module"],
'''

    new_eval_return = '''        "answer_strategy_mode": analysis["answer_strategy_mode"],
        "answer_boundary_note_type": analysis["answer_boundary_note_type"],
        "risk_boundary_handled": analysis["risk_boundary_handled"],
        "answer_primary_module": analysis["answer_primary_module"],
'''

    if '"risk_boundary_handled": analysis["risk_boundary_handled"]' not in content:
        if old_eval_return not in content:
            errors.append("evaluate_case return anchor not found")
        else:
            content = content.replace(old_eval_return, new_eval_return, 1)
            changes.append("added risk_boundary fields to evaluate_case return")
    else:
        changes.append("risk_boundary fields already in evaluate_case return")

    old_summary_gate = '''        if result["handoff_required"]
        or result["answer_handoff_required"]
        or result["answer_safety_blocked"]
        or result["render_safety_blocked"]
'''

    new_summary_gate = '''        if result["handoff_required"]
        or result["answer_handoff_required"]
        or result["answer_safety_blocked"]
        or result["render_safety_blocked"]
        or result.get("risk_boundary_handled") is True
'''

    if 'or result.get("risk_boundary_handled") is True' not in content:
        if old_summary_gate not in content:
            errors.append("summary risk gate pass anchor not found")
        else:
            content = content.replace(old_summary_gate, new_summary_gate, 1)
            changes.append("updated summary risk_gate_pass_count")
    else:
        changes.append("summary risk_gate_pass_count already includes risk boundary")

    old_failed_case_fields = '''            "answer_strategy_mode": result["answer_strategy_mode"],
            "failure_reasons": result["failure_reasons"],
'''

    new_failed_case_fields = '''            "answer_strategy_mode": result["answer_strategy_mode"],
            "answer_boundary_note_type": result.get("answer_boundary_note_type"),
            "risk_boundary_handled": result.get("risk_boundary_handled"),
            "failure_reasons": result["failure_reasons"],
'''

    if '"risk_boundary_handled": result.get("risk_boundary_handled")' not in content:
        if old_failed_case_fields not in content:
            errors.append("failed_cases field anchor not found")
        else:
            content = content.replace(old_failed_case_fields, new_failed_case_fields, 1)
            changes.append("added risk_boundary fields to failed_cases summary")
    else:
        changes.append("risk_boundary fields already in failed_cases summary")

    if content != original and not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")


def patch_config_m14(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Restore M14 as boundary/handoff fragment."""

    if not CONFIG_FILE.exists():
        errors.append(f"missing strategy config file: {CONFIG_FILE}")
        return

    config: dict[str, Any] = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    fragments = config.get("handoff_risk_fragments")

    if not isinstance(fragments, list):
        errors.append("handoff_risk_fragments is not a list")
        return

    if "M14" in fragments:
        changes.append("M14 already present in handoff_risk_fragments")
    else:
        insert_at = fragments.index("USB接口") if "USB接口" in fragments else 0
        fragments.insert(insert_at, "M14")
        CONFIG_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changes.append("restored M14 to handoff_risk_fragments")


def patch_target_check_expectation(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Update targeted check TC_SPEC_021 expectation after M14 contract correction."""

    if not TARGET_CHECK_FILE.exists():
        changes.append("targeted check file not present; skipped")
        return

    content = TARGET_CHECK_FILE.read_text(encoding="utf-8")
    original = content

    old_block = '''    TargetCase(
        case_id="TC_SPEC_021",
        query="你们有没有M14螺纹的球头",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="single_primary",
        expected_handoff_required=False,
    ),
'''

    new_block = '''    TargetCase(
        case_id="TC_SPEC_021",
        query="你们有没有M14螺纹的球头",
        selected_module="spec",
        candidate_modules=("spec",),
        expected_strategy_mode="handoff_required",
        expected_handoff_required=True,
    ),
'''

    if old_block in content:
        content = content.replace(old_block, new_block, 1)
        TARGET_CHECK_FILE.write_text(content, encoding="utf-8")
        changes.append("updated TC_SPEC_021 targeted expectation to handoff")
    elif "case_id=\"TC_SPEC_021\"" in content:
        changes.append("TC_SPEC_021 targeted expectation already customized")
    else:
        changes.append("TC_SPEC_021 not found in targeted check; skipped")

    _ = original


if __name__ == "__main__":
    raise SystemExit(main())