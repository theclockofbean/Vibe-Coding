"""Fix Phase 3-I-H frontend contract checker mypy error."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ih_frontend_payload_contract.py"
)


def main() -> int:
    """Patch frontend contract checker."""

    print("=" * 80)
    print("fixing Phase 3-I-H frontend contract checker mypy error")

    if not CHECK_FILE.exists():
        pprint({"error": f"missing check file: {CHECK_FILE}"})
        return 1

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content

    old_line = "    payload = state_to_response_payload(sample_state)\n"
    new_line = "    payload = state_to_response_payload(cast(Any, sample_state))\n"

    if old_line not in content:
        if new_line in content:
            pprint(
                {
                    "check_file": str(CHECK_FILE),
                    "changed": False,
                    "message": "already patched",
                }
            )
            return 0

        pprint({"error": "state_to_response_payload call anchor not found"})
        return 1

    content = content.replace(old_line, new_line, 1)

    if "from typing import Any, Final" in content:
        content = content.replace(
            "from typing import Any, Final",
            "from typing import Any, Final, cast",
            1,
        )

    CHECK_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "check_file": str(CHECK_FILE),
            "changed": content != original,
            "fix": "cast sample_state as Any for state_to_response_payload",
        }
    )

    print("Phase 3-I-H frontend contract checker mypy error fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())