"""Ensure Spec KB workflow writes final retrieval metadata."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"


ANCHOR: Final[str] = '''        metadata["retrieval_source"] = "real_spec_kb"
        metadata["retrieval_collection_name"] = collection_name

        return new_state, True
'''

REPLACEMENT: Final[str] = '''        metadata["retrieval_source"] = "real_spec_kb"
        metadata["retrieval_collection_name"] = collection_name
        metadata["retrieval_selected_module"] = "spec"
        metadata["retrieval_hit_count"] = len(retrieved_chunks)

        cast(dict[str, Any], new_state)["retrieval_selected_module"] = "spec"
        cast(dict[str, Any], new_state)["retrieval_hit_count"] = len(retrieved_chunks)

        return new_state, True
'''


def main() -> int:
    """Patch workflow metadata."""

    print("=" * 80)
    print("fixing final Spec KB retrieval metadata")

    if not WORKFLOW_FILE.exists():
        pprint({"error": f"missing workflow file: {WORKFLOW_FILE}"})
        return 1

    content = WORKFLOW_FILE.read_text(encoding="utf-8")

    if 'metadata["retrieval_selected_module"] = "spec"' in content:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "changed": False,
                "already_fixed": True,
            }
        )
        return 0

    if ANCHOR not in content:
        pprint(
            {
                "workflow_file": str(WORKFLOW_FILE),
                "error": "Spec metadata anchor not found",
            }
        )
        return 1

    content = content.replace(ANCHOR, REPLACEMENT, 1)
    WORKFLOW_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "workflow_file": str(WORKFLOW_FILE),
            "changed": True,
            "added": [
                'metadata["retrieval_selected_module"]',
                'metadata["retrieval_hit_count"]',
                'state["retrieval_selected_module"]',
                'state["retrieval_hit_count"]',
            ],
        }
    )

    print("Spec KB final metadata fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())