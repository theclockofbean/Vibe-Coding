# ruff: noqa: E402,I001
"""Check Phase 3-I-H API response payload regression."""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Any, Final, cast

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
API_ROOT: Final[Path] = BACKEND_ROOT / "app/api"
AGENT_API_FILE: Final[Path] = BACKEND_ROOT / "app/api/v1/agent.py"

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
    "answer_forbidden_fragments",
    "answer_boundary_note_type",
    "answer_strategy_reason",
)

REQUIRED_API_FRAGMENTS: Final[tuple[str, ...]] = (
    "state_to_response_payload",
    "run_agent_workflow",
)


def main() -> int:
    """Run API response payload regression check."""

    print("=" * 80)
    print("checking Phase 3-I-H API response payload regression")

    errors: list[str] = []

    api_result = inspect_api_layer(errors=errors)
    payload_result = check_payload_contract(errors=errors)

    result = {
        "api_result": api_result,
        "payload_result": payload_result,
        "errors": errors,
    }

    pprint(result)

    if errors:
        print("Phase 3-I-H API response payload regression check failed")
        return 1

    print("Phase 3-I-H API response payload regression check passed")
    return 0


def inspect_api_layer(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Inspect API layer for workflow payload serialization."""

    if not API_ROOT.exists():
        errors.append(f"missing API root: {API_ROOT}")
        return {"api_root": str(API_ROOT), "exists": False}

    matched_files: list[dict[str, Any]] = []

    for path in sorted(API_ROOT.rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        matched = [
            fragment
            for fragment in REQUIRED_API_FRAGMENTS
            if fragment in content
        ]

        if matched:
            matched_files.append(
                {
                    "path": str(path.relative_to(BACKEND_ROOT)),
                    "matched_fragments": matched,
                }
            )

    return {
        "api_root": str(API_ROOT),
        "agent_api_file_exists": AGENT_API_FILE.exists(),
        "matched_files": matched_files,
        "direct_workflow_payload_reference_found": bool(matched_files),
        "note": (
            "Direct API reference is audit-only because API payload "
            "serialization may be indirect."
        ),
    }


def check_payload_contract(
    *,
    errors: list[str],
) -> dict[str, Any]:
    """Check API-facing payload contract preserves answer strategy fields."""

    state: dict[str, Any] = {
        "session_id": "phase3ih-h3-session",
        "conversation_id": "phase3ih-h3-conversation",
        "user_text": "便宜点能包邮吗？",
        "final_response": "该问题涉及高风险业务承诺，不能直接给出确定性答复。",
        "answer_text": "该问题涉及高风险业务承诺，不能直接给出确定性答复。",
        "selected_module": "price",
        "intent": "price",
        "candidate_modules": ["price", "logistics"],
        "handoff_required": True,
        "human_handoff": True,
        "response_sources": [],
        "response_warnings": ["answer strategy safety gate applied"],
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

    payload = state_to_response_payload(cast(Any, state))
    metadata = payload.get("metadata")

    if not isinstance(metadata, dict):
        errors.append("API-facing payload metadata must be dict")
        metadata = {}

    missing_top_level = [
        field
        for field in REQUIRED_ANSWER_STRATEGY_FIELDS
        if field not in payload
    ]
    missing_metadata = [
        field
        for field in REQUIRED_ANSWER_STRATEGY_FIELDS
        if field not in metadata
    ]

    if missing_top_level:
        errors.append(f"missing top-level answer strategy fields: {missing_top_level}")

    if missing_metadata:
        errors.append(f"missing metadata answer strategy fields: {missing_metadata}")

    if payload.get("answer_strategy_mode") != "safety_blocked":
        errors.append("answer_strategy_mode mismatch")

    if payload.get("answer_primary_module") != "price":
        errors.append("answer_primary_module mismatch")

    if payload.get("answer_handoff_required") is not True:
        errors.append("answer_handoff_required must be true")

    if payload.get("answer_safety_blocked") is not True:
        errors.append("answer_safety_blocked must be true")

    return {
        "payload_keys": sorted(payload),
        "metadata_keys": sorted(metadata),
        "answer_strategy_mode": payload.get("answer_strategy_mode"),
        "answer_primary_module": payload.get("answer_primary_module"),
        "answer_candidate_modules": payload.get("answer_candidate_modules"),
        "answer_handoff_required": payload.get("answer_handoff_required"),
        "answer_safety_blocked": payload.get("answer_safety_blocked"),
        "missing_top_level": missing_top_level,
        "missing_metadata": missing_metadata,
    }


if __name__ == "__main__":
    raise SystemExit(main())