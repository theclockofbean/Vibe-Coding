"""Insert spec fact with risk boundary branch into answer strategy."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
STRATEGY_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/answering/multimodule_answer_strategy.py"
)


HELPER_FUNCTION: Final[str] = '''
def should_answer_spec_fact_with_risk_boundary(
    *,
    selected_module: str | None,
    handoff_risk_fragments: list[str],
) -> bool:
    """Return whether spec facts may answer with a risk boundary note."""

    if selected_module != "spec":
        return False

    if not handoff_risk_fragments:
        return False

    spec_fact_boundary_fragments = {
        "安装",
        "怎么安装",
        "怎么装",
        "适配",
        "车型",
        "宝马",
        "USB接口",
        "温控",
    }

    return set(handoff_risk_fragments) <= spec_fact_boundary_fragments
'''


OLD_HANDOFF_BLOCK: Final[str] = '''    if handoff_risk_fragments:
        return build_decision(
            mode=HANDOFF_MODE,
            selected_module=selected_module,
            candidate_modules=normalized_candidates,
            boundary_note_type="risk_handoff_required",
            forbidden_fragments=[],
            config=config,
            reason="risk handoff fragment detected",
        )

'''


NEW_HANDOFF_BLOCK: Final[str] = '''    if handoff_risk_fragments and should_answer_spec_fact_with_risk_boundary(
        selected_module=selected_module,
        handoff_risk_fragments=handoff_risk_fragments,
    ):
        return build_decision(
            mode="primary_with_boundary_note",
            selected_module=selected_module,
            candidate_modules=normalized_candidates,
            boundary_note_type="risk_handoff_required",
            forbidden_fragments=[],
            config=config,
            reason="spec fact answer with risk boundary",
        )

    if handoff_risk_fragments:
        return build_decision(
            mode=HANDOFF_MODE,
            selected_module=selected_module,
            candidate_modules=normalized_candidates,
            boundary_note_type="risk_handoff_required",
            forbidden_fragments=[],
            config=config,
            reason="risk handoff fragment detected",
        )

'''


def main() -> int:
    """Patch strategy branch."""

    print("=" * 80)
    print("fixing Phase 3-I-I spec fact boundary branch")

    errors: list[str] = []
    changes: list[str] = []

    if not STRATEGY_FILE.exists():
        errors.append(f"missing strategy file: {STRATEGY_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = STRATEGY_FILE.read_text(encoding="utf-8")
    original = content

    if "def should_answer_spec_fact_with_risk_boundary(" not in content:
        anchor = "\ndef detect_handoff_risk_fragments("
        if anchor not in content:
            errors.append("helper insertion anchor not found")
        else:
            content = content.replace(anchor, HELPER_FUNCTION + "\n" + anchor, 1)
            changes.append("inserted should_answer_spec_fact_with_risk_boundary helper")
    else:
        changes.append("helper already present")

    if "spec fact answer with risk boundary" in content:
        changes.append("spec boundary branch already present")
    elif OLD_HANDOFF_BLOCK in content:
        content = content.replace(OLD_HANDOFF_BLOCK, NEW_HANDOFF_BLOCK, 1)
        changes.append("inserted spec boundary branch before full handoff")
    else:
        errors.append("handoff decision block not found")

    if content != original and not errors:
        STRATEGY_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I spec fact boundary branch fix failed")
        return 1

    print("Phase 3-I-I spec fact boundary branch fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())