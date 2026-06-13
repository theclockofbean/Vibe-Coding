"""Record static-check cleanup for Phase 3-I-C10.

This script is intentionally kept lightweight because the actual cleanup has
already been applied to workflow.py and the route override patch script.
"""

from __future__ import annotations


def main() -> int:
    """Confirm Phase 3-I-C10 static debt cleanup script is present."""

    print("Phase 3-I-C10 static debt cleanup recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())