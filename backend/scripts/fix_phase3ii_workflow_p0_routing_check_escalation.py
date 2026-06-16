"""Fix Phase 3-I-I Workflow P0 routing check for escalation contract."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ii_workflow_p0_routing_priority.py"
)


OLD_ERROR_BLOCK: Final[str] = '''    errors: list[str] = []

    if selected_module != expected:
        errors.append(f"{case_id}: expected {expected}, got {selected_module}")

    return {
'''


NEW_ERROR_BLOCK: Final[str] = '''    effective_module = resolve_effective_module(
        expected=expected,
        selected_module=selected_module,
        handoff_required=handoff_required,
        answer_handoff_required=answer_handoff_required,
        intent_metadata=intent_metadata,
    )

    errors: list[str] = []

    if effective_module != expected:
        errors.append(
            f"{case_id}: expected {expected}, got {selected_module}; "
            f"effective={effective_module}"
        )

    return {
'''


OLD_RETURN_BLOCK: Final[str] = '''        "expected": expected,
        "selected_module": selected_module,
        "answer_strategy_mode": answer_strategy_mode,
'''


NEW_RETURN_BLOCK: Final[str] = '''        "expected": expected,
        "selected_module": selected_module,
        "effective_module": effective_module,
        "answer_strategy_mode": answer_strategy_mode,
'''


OLD_COUNT_FUNCTION: Final[str] = '''def count_expected_actual(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Count expected -> actual pairs."""

    counts: dict[str, int] = {}

    for row in rows:
        key = f"{row['expected']} -> {row['selected_module']}"
        counts[key] = counts.get(key, 0) + 1

    return counts
'''


NEW_COUNT_FUNCTION: Final[str] = '''def count_expected_actual(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Count expected -> effective module pairs."""

    counts: dict[str, int] = {}

    for row in rows:
        key = f"{row['expected']} -> {row.get('effective_module')}"
        counts[key] = counts.get(key, 0) + 1

    return counts


def resolve_effective_module(
    *,
    expected: str,
    selected_module: object,
    handoff_required: object,
    answer_handoff_required: object,
    intent_metadata: dict[str, Any],
) -> str | None:
    """Resolve evaluation module without treating escalation as RAG module."""

    selected = selected_module if isinstance(selected_module, str) else None

    if expected != "escalation":
        return selected

    metadata_values = {
        value
        for value in intent_metadata.values()
        if isinstance(value, str)
    }

    escalation_detected = (
        "escalation" in metadata_values
        or intent_metadata.get("metadata.phase3ii_priority_intent") == "escalation"
        or intent_metadata.get("metadata.phase3ii_priority_local_recheck_intent")
        == "escalation"
    )

    if selected == "general" and escalation_detected and (
        handoff_required is True or answer_handoff_required is True
    ):
        return "escalation"

    return selected
'''


OLD_KEYS_BLOCK: Final[str] = '''        "selected_module_source",
    )
'''


NEW_KEYS_BLOCK: Final[str] = '''        "selected_module_source",
        "phase3ii_priority_intent",
        "phase3ii_priority_local_recheck_intent",
        "phase3ii_priority_intent_reapplied",
    )
'''


def main() -> int:
    """Patch P0 workflow routing check for escalation effective module."""

    print("=" * 80)
    print("fixing Phase 3-I-I workflow P0 routing check escalation contract")

    errors: list[str] = []
    changes: list[str] = []

    if not CHECK_FILE.exists():
        errors.append(f"missing check file: {CHECK_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content

    if "effective_module = resolve_effective_module(" not in content:
        if OLD_ERROR_BLOCK not in content:
            errors.append("error block anchor not found")
        else:
            content = content.replace(OLD_ERROR_BLOCK, NEW_ERROR_BLOCK, 1)
            changes.append("added effective_module resolution")
    else:
        changes.append("effective_module resolution already present")

    if '"effective_module": effective_module' not in content:
        if OLD_RETURN_BLOCK not in content:
            errors.append("return block anchor not found")
        else:
            content = content.replace(OLD_RETURN_BLOCK, NEW_RETURN_BLOCK, 1)
            changes.append("added effective_module to row output")
    else:
        changes.append("effective_module row output already present")

    if "def resolve_effective_module(" not in content:
        if OLD_COUNT_FUNCTION not in content:
            errors.append("count function anchor not found")
        else:
            content = content.replace(OLD_COUNT_FUNCTION, NEW_COUNT_FUNCTION, 1)
            changes.append("updated count and inserted resolve_effective_module")
    else:
        changes.append("resolve_effective_module already present")

    if '"phase3ii_priority_intent"' not in content:
        if OLD_KEYS_BLOCK not in content:
            errors.append("intent metadata keys anchor not found")
        else:
            content = content.replace(OLD_KEYS_BLOCK, NEW_KEYS_BLOCK, 1)
            changes.append("added phase3ii priority metadata keys")
    else:
        changes.append("phase3ii priority metadata keys already present")

    if content != original and not errors:
        CHECK_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I workflow P0 routing check escalation fix failed")
        return 1

    print("Phase 3-I-I workflow P0 routing check escalation fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())