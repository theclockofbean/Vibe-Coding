# ruff: noqa: E402,I001
"""Check Phase 3-I-H response payload baseline for answer strategy fields."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
STATE_FILE: Final[Path] = BACKEND_ROOT / "app/agent/state.py"
WORKFLOW_FILE: Final[Path] = BACKEND_ROOT / "app/agent/workflow.py"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import state_to_response_payload


REQUIRED_ANSWER_STRATEGY_FIELDS: Final[tuple[str, ...]] = (
    "answer_strategy_mode",
    "answer_primary_module",
    "answer_candidate_modules",
    "answer_boundary_notes",
    "answer_split_required",
    "answer_handoff_required",
    "answer_safety_blocked",
    "answer_forbidden_commitment_detected",
)

REQUIRED_WORKFLOW_FRAGMENTS: Final[tuple[str, ...]] = (
    "_apply_answer_strategy_metadata",
    "_apply_answer_strategy_render_gate",
    "answer_strategy_mode",
    "answer_boundary_notes",
    "answer_safety_blocked",
)

REQUIRED_STATE_FRAGMENTS: Final[tuple[str, ...]] = (
    "state_to_response_payload",
    "final_response",
    "metadata",
)


def main() -> int:
    """Run response payload baseline check."""

    print("=" * 80)
    print("checking Phase 3-I-H response payload baseline")

    errors: list[str] = []

    workflow_result = check_file_fragments(
        path=WORKFLOW_FILE,
        required_fragments=REQUIRED_WORKFLOW_FRAGMENTS,
        errors=errors,
    )
    state_result = check_file_fragments(
        path=STATE_FILE,
        required_fragments=REQUIRED_STATE_FRAGMENTS,
        errors=errors,
    )
    payload_result = check_response_payload(errors=errors)

    result = {
        "workflow_result": workflow_result,
        "state_result": state_result,
        "payload_result": payload_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-H response payload baseline check failed")
        return 1

    print("Phase 3-I-H response payload baseline check passed")
    return 0


def check_file_fragments(
    *,
    path: Path,
    required_fragments: tuple[str, ...],
    errors: list[str],
) -> dict[str, Any]:
    """Check required fragments in file."""

    if not path.exists():
        errors.append(f"missing file: {path}")
        return {"path": str(path), "exists": False}

    content = path.read_text(encoding="utf-8")
    missing: list[str] = []

    for fragment in required_fragments:
        if fragment not in content:
            missing.append(fragment)
            errors.append(f"{path.name}: missing fragment: {fragment}")

    return {
        "path": str(path),
        "exists": True,
        "required_count": len(required_fragments),
        "missing": missing,
    }


def check_response_payload(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check whether answer strategy fields appear in response payload."""

    sample_state: dict[str, Any] = {
        "session_id": "phase3ih-baseline-session",
        "conversation_id": "phase3ih-baseline-conversation",
        "user_text": "便宜点能包邮吗？",
        "final_response": "该问题涉及需要进一步确认的信息，不能直接给出确定性答复。",
        "answer_text": "该问题涉及需要进一步确认的信息，不能直接给出确定性答复。",
        "selected_module": "price",
        "intent": "price",
        "candidate_modules": ["price", "logistics"],
        "handoff_required": True,
        "human_handoff": True,
        "response_sources": [],
        "response_warnings": [],
        "risk_flags": ["answer_strategy_safety_blocked"],
        "metadata": {
            "answer_strategy_mode": "safety_blocked",
            "answer_primary_module": "price",
            "answer_candidate_modules": ["price", "logistics"],
            "answer_boundary_notes": [],
            "answer_split_required": False,
            "answer_handoff_required": True,
            "answer_safety_blocked": True,
            "answer_forbidden_commitment_detected": False,
            "answer_forbidden_fragments": [],
            "answer_boundary_note_type": "price_logistics_commitment_risk",
            "answer_strategy_reason": "matched configured module pair rule",
            "render_mode": "answer_strategy_safety_blocked",
            "render_safety_blocked": True,
        },
    }

    payload = state_to_response_payload(cast(Any, sample_state))

    if not isinstance(payload, dict):
        errors.append("state_to_response_payload must return dict")
        return {"payload_type": type(payload).__name__}

    top_level_keys = set(payload)
    metadata = payload.get("metadata")
    metadata_keys = set(metadata) if isinstance(metadata, dict) else set()

    missing_from_top_level = [
        field
        for field in REQUIRED_ANSWER_STRATEGY_FIELDS
        if field not in top_level_keys
    ]
    missing_from_metadata = [
        field
        for field in REQUIRED_ANSWER_STRATEGY_FIELDS
        if field not in metadata_keys
    ]

    # H1 is a baseline audit, so missing answer strategy fields are reported but
    # not treated as failure yet. H2 will implement the minimal exposure patch.
    return {
        "payload_keys": sorted(top_level_keys),
        "metadata_is_dict": isinstance(metadata, dict),
        "metadata_keys": sorted(metadata_keys),
        "answer_strategy_fields_missing_from_top_level": missing_from_top_level,
        "answer_strategy_fields_missing_from_metadata": missing_from_metadata,
        "needs_h2_payload_patch": bool(
            missing_from_top_level and missing_from_metadata
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())