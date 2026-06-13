"""Fix missing cast runtime error in state answer strategy payload exposure."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
STATE_FILE: Final[Path] = BACKEND_ROOT / "app/agent/state.py"


def main() -> int:
    """Replace cast-based TypedDict copy with plain dict copy."""

    print("=" * 80)
    print("fixing Phase 3-I-H payload cast runtime error")

    if not STATE_FILE.exists():
        pprint({"error": f"missing state file: {STATE_FILE}"})
        return 1

    content = STATE_FILE.read_text(encoding="utf-8")
    original = content

    old_line = '    state_values = cast(dict[str, Any], state)\n'
    new_line = '    state_values: dict[str, Any] = dict(state)\n'

    if old_line not in content:
        if new_line in content:
            pprint(
                {
                    "state_file": str(STATE_FILE),
                    "changed": False,
                    "message": "already patched",
                }
            )
            return 0

        pprint({"error": "cast state_values anchor not found"})
        return 1

    content = content.replace(old_line, new_line, 1)

    STATE_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "state_file": str(STATE_FILE),
            "changed": content != original,
            "fix": "replace cast(dict[str, Any], state) with dict(state)",
        }
    )

    print("Phase 3-I-H payload cast runtime error fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())