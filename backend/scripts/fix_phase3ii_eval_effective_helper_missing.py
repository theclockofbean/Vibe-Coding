"""Fix missing effective escalation module helper in evaluator."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EVAL_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_real_llm_50_case_eval.py"
CHECK_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_phase3ii_eval_effective_escalation_module.py"


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
    """Fix evaluator helper and check script unused ignore."""

    print("=" * 80)
    print("fixing Phase 3-I-I evaluator effective helper missing")

    errors: list[str] = []
    changes: list[str] = []

    patch_eval_file(errors=errors, changes=changes)
    patch_check_file(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I evaluator effective helper fix failed")
        return 1

    print("Phase 3-I-I evaluator effective helper fix completed")
    return 0


def patch_eval_file(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch evaluator file."""

    if not EVAL_FILE.exists():
        errors.append(f"missing evaluator file: {EVAL_FILE}")
        return

    content = EVAL_FILE.read_text(encoding="utf-8")
    original = content

    if "def resolve_effective_selected_module(" in content:
        changes.append("resolve_effective_selected_module already present")
    else:
        anchor = "\ndef is_risk_case("
        fallback_anchor = "\ndef "

        if anchor in content:
            content = content.replace(anchor, HELPER_FUNCTION + "\n" + anchor, 1)
            changes.append("inserted helper before is_risk_case")
        elif fallback_anchor in content:
            content = content.replace(
                fallback_anchor,
                HELPER_FUNCTION + "\n" + fallback_anchor,
                1,
            )
            changes.append("inserted helper before first function")
        else:
            errors.append("no function anchor found in evaluator")
            return

    if content != original:
        EVAL_FILE.write_text(content, encoding="utf-8")


def patch_check_file(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch check file unused ignore."""

    if not CHECK_FILE.exists():
        errors.append(f"missing check file: {CHECK_FILE}")
        return

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content

    old = "    return module  # type: ignore[return-value]\n"
    new = "    return module\n"

    if old in content:
        content = content.replace(old, new, 1)
        changes.append("removed unused return-value type ignore")
    else:
        changes.append("unused return-value type ignore already absent")

    if content != original:
        CHECK_FILE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())