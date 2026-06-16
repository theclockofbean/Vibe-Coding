"""Inspect grounded_renderer.py only."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
RENDERER_FILE: Final[Path] = BACKEND_ROOT / "app/agent/rendering/grounded_renderer.py"


WINDOWS: Final[tuple[tuple[int, int], ...]] = (
    (1, 120),
    (160, 230),
    (250, 315),
    (360, 410),
)


def main() -> int:
    """Print focused renderer windows."""

    print("=" * 80)
    print("inspecting Phase 3-I-I grounded_renderer.py only")

    errors: list[str] = []

    if not RENDERER_FILE.exists():
        errors.append(f"missing renderer file: {RENDERER_FILE}")
        pprint({"errors": errors})
        return 1

    lines = RENDERER_FILE.read_text(encoding="utf-8").splitlines()

    result = {
        "file": str(RENDERER_FILE.relative_to(BACKEND_ROOT)),
        "line_count": len(lines),
        "windows": {
            f"{start}_{end}": [
                f"{line_number}: {lines[line_number - 1]}"
                for line_number in range(start, min(end, len(lines)) + 1)
            ]
            for start, end in WINDOWS
        },
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-I grounded_renderer.py inspection failed")
        return 1

    print("Phase 3-I-I grounded_renderer.py inspection passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())