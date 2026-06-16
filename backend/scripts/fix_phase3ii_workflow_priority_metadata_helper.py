"""Fix Phase 3-I-I workflow priority reapply metadata helper name."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


def main() -> int:
    """Replace nonexistent _state_metadata with existing _ensure_metadata."""

    print("=" * 80)
    print("fixing Phase 3-I-I workflow priority metadata helper")

    errors: list[str] = []
    changes: list[str] = []

    if not WORKFLOW_FILE.exists():
        errors.append(f"missing workflow file: {WORKFLOW_FILE}")
        pprint({"changes": changes, "errors": errors})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    old = "    metadata = _state_metadata(state)\n"
    new = "    metadata = _ensure_metadata(state)\n"

    if old in content:
        content = content.replace(old, new, 1)
        changes.append("replaced _state_metadata(state) with _ensure_metadata(state)")
    elif new in content:
        changes.append("metadata helper already fixed")
    else:
        errors.append("metadata helper anchor not found")

    if content != original and not errors:
        WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint({"changes": changes, "errors": errors})

    if errors:
        print("Phase 3-I-I workflow priority metadata helper fix failed")
        return 1

    print("Phase 3-I-I workflow priority metadata helper fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())