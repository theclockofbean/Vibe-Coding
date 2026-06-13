# ruff: noqa: E402,I001
"""Check answer strategy fields exposed in response payload."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.state import state_to_response_payload


REQUIRED_FIELDS: Final[tuple[str, ...]] = (
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


def main() -> int:
    """Run response payload answer strategy exposure check."""

    print("=" * 80)
    print("checking response payload answer strategy field exposure")

    errors: list[str] = []

    payload = build_payload()
    metadata = payload.get("metadata")

    if not isinstance(metadata, dict):
        errors.append("payload metadata must be dict")
        metadata = {}

    missing_top_level = [
        field
        for field in REQUIRED_FIELDS
        if field not in payload
    ]

    missing_metadata = [
        field
        for field in REQUIRED_FIELDS
        if field not in metadata
    ]

    if missing_top_level:
        errors.append(f"missing top-level fields: {missing_top_level}")

    if missing_metadata:
        errors.append(f"missing metadata fields: {missing_metadata}")

    if payload.get("answer_strategy_mode") != "safety_blocked":
        errors.append("answer_strategy_mode mismatch")

    if payload.get("answer_primary_module") != "price":
        errors.append("answer_primary_module mismatch")

    if payload.get("answer_safety_blocked") is not True:
        errors.append("answer_safety_blocked must be true")

    if payload.get("answer_handoff_required") is not True:
        errors.append("answer_handoff_required must be true")

    result = {
        "payload_keys": sorted(payload),
        "metadata_keys": sorted(metadata),
        "answer_strategy_mode": payload.get("answer_strategy_mode"),
        "answer_primary_module": payload.get("answer_primary_module"),
        "answer_candidate_modules": payload.get("answer_candidate_modules"),
        "answer_safety_blocked": payload.get("answer_safety_blocked"),
        "answer_handoff_required": payload.get("answer_handoff_required"),
        "missing_top_level": missing_top_level,
        "missing_metadata": missing_metadata,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("response payload answer strategy field exposure check failed")
        return 1

    print("response payload answer strategy field exposure check passed")
    return 0


def build_payload() -> dict[str, Any]:
    """Build sample response payload."""

    sample_state: dict[str, Any] = {
        "session_id": "phase3ih-h2-session",
        "conversation_id": "phase3ih-h2-conversation",
        "user_text": "便宜点能包邮吗？",
        "final_response": "该问题涉及高风险业务承诺，不能直接给出确定性答复。",
        "answer_text": "该问题涉及高风险业务承诺，不能直接给出确定性答复。",
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
            "answer_forbidden_commitment_detected": True,
            "answer_forbidden_fragments": ["包邮"],
            "answer_boundary_note_type": "price_logistics_commitment_risk",
            "answer_strategy_reason": "matched configured module pair rule",
            "render_mode": "answer_strategy_safety_blocked",
            "render_safety_blocked": True,
        },
    }

    payload = state_to_response_payload(cast(Any, sample_state))

    return payload


if __name__ == "__main__":
    raise SystemExit(main())