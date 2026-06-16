"""Normalize selected_module in response payload from final answer strategy metadata."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

STATE_FILE = Path("app/agent/state.py")


OLD_LINE = '''        "selected_module": state.get("selected_module"),
'''


NEW_LINE = '''        "selected_module": _response_selected_module(state),
'''


HELPER = '''

def _response_selected_module(state: AgentState) -> str | None:
    """Return selected module normalized from final answer strategy metadata."""

    selected_module = state.get("selected_module")
    metadata = state.get("metadata")

    if not isinstance(metadata, dict):
        return selected_module

    answer_primary_module = metadata.get("answer_primary_module")
    answer_candidate_modules = metadata.get("answer_candidate_modules")

    supported_modules = {"spec", "price", "logistics", "quality"}

    if answer_primary_module not in supported_modules:
        return selected_module

    if isinstance(answer_candidate_modules, list):
        clean_candidates = [
            item for item in answer_candidate_modules if isinstance(item, str)
        ]

        if clean_candidates == [answer_primary_module]:
            return answer_primary_module

    return selected_module
'''


def main() -> int:
    content = STATE_FILE.read_text(encoding="utf-8")
    changes: list[str] = []
    errors: list[str] = []

    if OLD_LINE in content:
        content = content.replace(OLD_LINE, NEW_LINE, 1)
        changes.append("wired selected_module through response normalizer")
    elif "_response_selected_module(state)" in content:
        changes.append("selected_module normalizer already wired")
    else:
        errors.append("selected_module response payload anchor not found")

    if "def _response_selected_module(" not in content:
        content = content.rstrip() + HELPER + "\n"
        changes.append("added response selected_module normalizer")
    else:
        changes.append("response selected_module normalizer already present")

    if not errors:
        STATE_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())