"""Fix Phase 3-I-H payload exposure mypy errors."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
STATE_FILE: Final[Path] = BACKEND_ROOT / "app/agent/state.py"
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ih_response_payload_answer_strategy_fields.py"
)


def main() -> int:
    """Patch state.py and H2 check script."""

    print("=" * 80)
    print("fixing Phase 3-I-H payload mypy errors")

    errors: list[str] = []
    changes: list[str] = []

    if not STATE_FILE.exists():
        errors.append(f"missing state file: {STATE_FILE}")
    else:
        changes.extend(patch_state_file())

    if not CHECK_FILE.exists():
        errors.append(f"missing check file: {CHECK_FILE}")
    else:
        changes.extend(patch_check_file())

    result = {
        "state_file": str(STATE_FILE),
        "check_file": str(CHECK_FILE),
        "changes": changes,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-H payload mypy fix failed")
        return 1

    print("Phase 3-I-H payload mypy fix completed")
    return 0


def patch_state_file() -> list[str]:
    """Patch dynamic TypedDict access in state.py."""

    content = STATE_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    old_block = '''    state_metadata = state.get("metadata")

    if isinstance(state_metadata, dict):
        for field in ANSWER_STRATEGY_RESPONSE_FIELDS:
            if field in state_metadata and field not in payload_metadata:
                payload_metadata[field] = state_metadata[field]

    for field in ANSWER_STRATEGY_RESPONSE_FIELDS:
        if field in enriched_payload:
            continue

        if field in payload_metadata:
            enriched_payload[field] = payload_metadata[field]
            continue

        if field in state:
            enriched_payload[field] = state[field]

    return enriched_payload
'''

    new_block = '''    state_metadata = state.get("metadata")
    state_values = cast(dict[str, Any], state)

    if isinstance(state_metadata, dict):
        for field in ANSWER_STRATEGY_RESPONSE_FIELDS:
            if field in state_metadata and field not in payload_metadata:
                payload_metadata[field] = state_metadata[field]

    for field in ANSWER_STRATEGY_RESPONSE_FIELDS:
        if field in enriched_payload:
            continue

        if field in payload_metadata:
            enriched_payload[field] = payload_metadata[field]
            continue

        if field in state_values:
            enriched_payload[field] = state_values[field]

    return enriched_payload
'''

    if old_block not in content:
        if "state_values = cast(dict[str, Any], state)" in content:
            return ["state.py already patched"]

        raise RuntimeError("state.py anchor block not found")

    content = content.replace(old_block, new_block, 1)

    if content != original:
        STATE_FILE.write_text(content, encoding="utf-8")
        changes.append("patched state.py dynamic TypedDict access")

    return changes


def patch_check_file() -> list[str]:
    """Patch redundant cast in H2 check script."""

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    old_line = "    return cast(dict[str, Any], payload)\n"
    new_line = "    return payload\n"

    if old_line not in content:
        if new_line in content:
            return ["check script already patched"]

        raise RuntimeError("check script redundant cast anchor not found")

    content = content.replace(old_line, new_line, 1)

    if content != original:
        CHECK_FILE.write_text(content, encoding="utf-8")
        changes.append("removed redundant cast in H2 check script")

    return changes


if __name__ == "__main__":
    raise SystemExit(main())