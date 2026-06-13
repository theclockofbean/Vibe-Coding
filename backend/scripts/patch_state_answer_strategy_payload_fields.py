"""Patch state_to_response_payload to expose answer strategy fields."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
STATE_FILE: Final[Path] = BACKEND_ROOT / "app/agent/state.py"

ORIGINAL_DEF: Final[str] = "def state_to_response_payload("
CORE_DEF: Final[str] = "def _state_to_response_payload_core("

HELPER_BLOCK: Final[str] = '''
ANSWER_STRATEGY_RESPONSE_FIELDS: tuple[str, ...] = (
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
    "answer_forbidden_fragments",
    "answer_boundary_note_type",
    "answer_strategy_reason",
)


def state_to_response_payload(
    state: AgentState,
) -> dict[str, Any]:
    """Convert state to response payload with answer strategy fields."""

    payload = _state_to_response_payload_core(state)

    return _expose_answer_strategy_payload_fields(
        state=state,
        payload=payload,
    )


def _expose_answer_strategy_payload_fields(
    *,
    state: AgentState,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Expose answer strategy fields at top level and metadata."""

    enriched_payload = dict(payload)
    payload_metadata = enriched_payload.get("metadata")

    if not isinstance(payload_metadata, dict):
        payload_metadata = {}
        enriched_payload["metadata"] = payload_metadata

    state_metadata = state.get("metadata")

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


def main() -> int:
    """Patch state.py."""

    print("=" * 80)
    print("patching state_to_response_payload answer strategy exposure")

    if not STATE_FILE.exists():
        pprint({"error": f"missing state file: {STATE_FILE}"})
        return 1

    content = STATE_FILE.read_text(encoding="utf-8")
    original = content

    if CORE_DEF in content and "ANSWER_STRATEGY_RESPONSE_FIELDS" in content:
        pprint(
            {
                "state_file": str(STATE_FILE),
                "changed": False,
                "message": "already patched",
            }
        )
        return 0

    if ORIGINAL_DEF not in content:
        pprint({"error": "state_to_response_payload definition not found"})
        return 1

    backup_file = STATE_FILE.with_suffix(
        ".before_answer_strategy_payload_patch_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".py"
    )
    backup_file.write_text(content, encoding="utf-8")

    content = content.replace(ORIGINAL_DEF, CORE_DEF, 1)
    content = content.rstrip() + "\n\n\n" + HELPER_BLOCK.strip() + "\n"

    STATE_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "state_file": str(STATE_FILE),
            "backup_file": str(backup_file),
            "changed": content != original,
            "exposed_fields": [
                "answer_strategy_mode",
                "answer_primary_module",
                "answer_candidate_modules",
                "answer_boundary_notes",
                "answer_split_required",
                "answer_handoff_required",
                "answer_safety_blocked",
                "answer_forbidden_commitment_detected",
                "answer_forbidden_fragments",
                "answer_boundary_note_type",
                "answer_strategy_reason",
            ],
        }
    )

    print("state_to_response_payload answer strategy exposure patch completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())