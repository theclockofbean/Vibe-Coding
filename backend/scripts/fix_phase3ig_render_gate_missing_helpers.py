"""Fix missing helper functions used by answer strategy render gate."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

HELPER_BLOCK: Final[str] = '''
def _as_dict(
    value: object,
) -> dict[str, Any]:
    """Return value as dict or empty dict."""

    if isinstance(value, dict):
        return cast(dict[str, Any], value)

    return {}


def _optional_text(
    value: object,
) -> str | None:
    """Return stripped text or None."""

    if not isinstance(value, str):
        return None

    stripped = value.strip()

    return stripped or None


def _merge_text_lists(
    left: list[str],
    right: list[str],
) -> list[str]:
    """Merge and deduplicate two text lists."""

    return _deduplicate_text_list([*left, *right])
'''


def main() -> int:
    """Patch workflow.py with missing render gate helpers."""

    print("=" * 80)
    print("fixing missing answer strategy render gate helpers")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    original = content

    missing_helpers = [
        helper_name
        for helper_name in ("_as_dict", "_optional_text", "_merge_text_lists")
        if f"def {helper_name}(" not in content
    ]

    if not missing_helpers:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "changed": False,
                "message": "helpers already exist",
            }
        )
        return 0

    content = content.rstrip() + "\n\n\n" + HELPER_BLOCK.strip() + "\n"

    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "changed": content != original,
            "added_helpers": missing_helpers,
        }
    )

    print("missing render gate helpers fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())