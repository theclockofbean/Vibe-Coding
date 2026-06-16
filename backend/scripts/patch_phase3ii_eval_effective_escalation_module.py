"""Patch Phase 3-I-I 50-case evaluator for effective escalation module."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"


HELPER_FUNCTION: Final[str] = '''
def resolve_effective_selected_module(
    *,
    expected_module: str,
    selected_module: object,
    handoff_required: bool,
    answer_handoff_required: bool,
    metadata: dict[str, object],
) -> str | None:
    """Resolve effective module for evaluation.

    Escalation is a business intent, not a RAG module. Workflow may keep
    selected_module as "general" to avoid passing an invalid module to RAG,
    while still storing escalation intent in metadata and triggering handoff.
    """

    selected = selected_module if isinstance(selected_module, str) else None

    if expected_module != "escalation":
        return selected

    metadata_values = {
        value
        for value in metadata.values()
        if isinstance(value, str)
    }

    nested_values: set[str] = set()

    for value in metadata.values():
        if not isinstance(value, dict):
            continue

        for nested_value in value.values():
            if isinstance(nested_value, str):
                nested_values.add(nested_value)

    escalation_detected = (
        "escalation" in metadata_values
        or "escalation" in nested_values
        or metadata.get("llm_intent") == "escalation"
        or metadata.get("phase3ii_priority_intent") == "escalation"
        or metadata.get("phase3ii_priority_local_recheck_intent") == "escalation"
    )

    if selected == "general" and escalation_detected and (
        handoff_required or answer_handoff_required
    ):
        return "escalation"

    return selected
'''


def main() -> int:
    """Patch evaluator effective escalation module."""

    print("=" * 80)
    print("patching Phase 3-I-I evaluator effective escalation module")

    errors: list[str] = []
    changes: list[str] = []

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    if "def resolve_effective_selected_module(" not in content:
        anchor = "\ndef is_risk_case("
        if anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(anchor, HELPER_FUNCTION + "\n" + anchor, 1)
            changes.append("inserted resolve_effective_selected_module helper")
    else:
        changes.append("resolve_effective_selected_module helper already present")

    selected_anchor = (
        "    selected_module = payload.get(\"selected_module\")\n"
    )

    effective_block = (
        "    effective_selected_module = resolve_effective_selected_module(\n"
        "        expected_module=expected_module,\n"
        "        selected_module=selected_module,\n"
        "        handoff_required=handoff_required,\n"
        "        answer_handoff_required=answer_handoff_required,\n"
        "        metadata=metadata,\n"
        "    )\n"
    )

    if "effective_selected_module = resolve_effective_selected_module(" not in content:
        if selected_anchor not in content:
            errors.append("selected_module anchor not found")
        else:
            content = content.replace(
                selected_anchor,
                selected_anchor + effective_block,
                1,
            )
            changes.append("added effective_selected_module resolution")
    else:
        changes.append("effective_selected_module resolution already present")

    old_mismatch = (
        "    if expected_module and selected_module != expected_module:\n"
        "        failure_reasons.append(\n"
        "            f\"MAJOR: selected_module expected {expected_module}, got {selected_module}\"\n"
        "        )\n"
    )

    new_mismatch = (
        "    if expected_module and effective_selected_module != expected_module:\n"
        "        failure_reasons.append(\n"
        "            f\"MAJOR: selected_module expected {expected_module}, \"\n"
        "            f\"got {selected_module}; effective={effective_selected_module}\"\n"
        "        )\n"
    )

    if old_mismatch in content:
        content = content.replace(old_mismatch, new_mismatch, 1)
        changes.append("updated selected_module mismatch to use effective module")
    elif "effective_selected_module != expected_module" in content:
        changes.append("selected_module mismatch already uses effective module")
    else:
        errors.append("selected_module mismatch anchor not found")

    old_result_field = (
        "        \"selected_module\": selected_module,\n"
    )

    new_result_field = (
        "        \"selected_module\": selected_module,\n"
        "        \"effective_selected_module\": effective_selected_module,\n"
    )

    if "\"effective_selected_module\":" not in content:
        if old_result_field not in content:
            errors.append("selected_module result field anchor not found")
        else:
            content = content.replace(old_result_field, new_result_field, 1)
            changes.append("added effective_selected_module to analysis result")
    else:
        changes.append("effective_selected_module result field already present")

    old_accuracy = (
        "        if result[\"selected_module\"] == result[\"expected_module\"]\n"
    )

    new_accuracy = (
        "        if result.get(\"effective_selected_module\", result[\"selected_module\"])\n"
        "        == result[\"expected_module\"]\n"
    )

    if old_accuracy in content:
        content = content.replace(old_accuracy, new_accuracy, 1)
        changes.append("updated module_accuracy calculation to use effective module")
    elif "effective_selected_module" in content and "module_accuracy" in content:
        changes.append("module_accuracy may already use effective module or needs manual review")
    else:
        changes.append("module_accuracy anchor not found; no change made")

    if content != original and not errors:
        EVAL_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator effective escalation module patch failed")
        return 1

    print("Phase 3-I-I evaluator effective escalation module patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())