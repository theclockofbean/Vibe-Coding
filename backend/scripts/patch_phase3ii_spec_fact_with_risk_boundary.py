"""Patch answer strategy: spec facts can answer with risk boundary."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CONFIG_FILE: Final[Path] = (
    PROJECT_ROOT / "docs/backend/phase3ig_multimodule_answer_strategy_v0.1.json"
)
STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)


PATCH_HELPER: Final[str] = '''
def should_answer_spec_fact_with_risk_boundary(
    *,
    selected_module: str | None,
    handoff_risk_fragments: list[str],
) -> bool:
    """Return whether spec facts should answer while risk part gets boundary.

    For spec route, fragments such as fitment, installation, USB usage, or
    temperature-control usage should not suppress structured SKU facts. The
    answer may provide SKU/thread/taper facts, while risky usage or fitment
    claims remain bounded by an artificial-confirmation note.
    """

    if selected_module != "spec":
        return False

    if not handoff_risk_fragments:
        return False

    spec_safe_fragments = {
        "锥度要求",
        "M14",
    }

    spec_mixed_risk_fragments = {
        "安装",
        "怎么安装",
        "怎么装",
        "适配",
        "车型",
        "宝马",
        "USB接口",
        "温控",
    }

    fragment_set = set(handoff_risk_fragments)

    return bool(fragment_set) and fragment_set <= (
        spec_safe_fragments | spec_mixed_risk_fragments
    )
'''


def main() -> int:
    """Patch config and strategy source."""

    print("=" * 80)
    print("patching Phase 3-I-I spec fact with risk boundary")

    errors: list[str] = []
    changes: list[str] = []

    patch_config(errors=errors, changes=changes)
    patch_strategy_source(errors=errors, changes=changes)

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec fact with risk boundary patch failed")
        return 1

    print("Phase 3-I-I spec fact with risk boundary patch completed")
    return 0


def patch_config(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Remove pure spec attributes from global handoff fragments."""

    if not CONFIG_FILE.exists():
        errors.append(f"missing config file: {CONFIG_FILE}")
        return

    content = CONFIG_FILE.read_text(encoding="utf-8")
    original = content

    for fragment in ("锥度要求", "M14"):
        old = f'    "{fragment}",\n'
        if old in content:
            content = content.replace(old, "", 1)
            changes.append(f"removed pure spec fragment from handoff config: {fragment}")

    if content != original:
        CONFIG_FILE.write_text(content, encoding="utf-8")
    else:
        changes.append("no pure spec handoff config fragment removed")


def patch_strategy_source(
    *,
    errors: list[str],
    changes: list[str],
) -> None:
    """Patch strategy source decision."""

    if not STRATEGY_FILE.exists():
        errors.append(f"missing strategy file: {STRATEGY_FILE}")
        return

    content = STRATEGY_FILE.read_text(encoding="utf-8")
    original = content

    if "def should_answer_spec_fact_with_risk_boundary(" not in content:
        anchor = "\ndef detect_handoff_risk_fragments("
        if anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(anchor, PATCH_HELPER + "\n" + anchor, 1)
            changes.append("inserted spec fact risk-boundary helper")
    else:
        changes.append("spec fact risk-boundary helper already present")

    old_block = '''    if handoff_risk_fragments:
        return AnswerStrategyDecision(
            mode=HANDOFF_MODE,
            primary_module=selected_module,
            candidate_modules=candidate_modules,
            boundary_note_type="risk_handoff_required",
            handoff_required=True,
            source_windows=source_windows,
            reason="risk handoff fragment detected",
        )

'''

    new_block = '''    if handoff_risk_fragments and should_answer_spec_fact_with_risk_boundary(
        selected_module=selected_module,
        handoff_risk_fragments=handoff_risk_fragments,
    ):
        return AnswerStrategyDecision(
            mode="primary_with_boundary_note",
            primary_module=selected_module,
            candidate_modules=candidate_modules,
            boundary_note_type="risk_handoff_required",
            source_windows=source_windows,
            reason="spec fact answer with risk boundary",
        )

    if handoff_risk_fragments:
        return AnswerStrategyDecision(
            mode=HANDOFF_MODE,
            primary_module=selected_module,
            candidate_modules=candidate_modules,
            boundary_note_type="risk_handoff_required",
            handoff_required=True,
            source_windows=source_windows,
            reason="risk handoff fragment detected",
        )

'''

    if old_block in content:
        content = content.replace(old_block, new_block, 1)
        changes.append("patched handoff decision with spec fact boundary branch")
    elif "spec fact answer with risk boundary" in content:
        changes.append("handoff decision already patched")
    else:
        errors.append("handoff decision block not found")

    if content != original and not errors:
        STRATEGY_FILE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())