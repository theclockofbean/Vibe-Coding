"""Evaluation report API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from fastapi import APIRouter, HTTPException

from app.core.config import PROJECT_ROOT

REPORT_FILE: Final[Path] = (
    PROJECT_ROOT / "logs" / "evaluation" / "phase3ii_real_llm_50_case_eval_report.json"
)

router = APIRouter(
    prefix="/evaluation",
    tags=["evaluation"],
)


@router.get("/latest")
def get_latest_evaluation() -> dict[str, Any]:
    """Return the latest regression/evaluation report."""

    if not REPORT_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=f"evaluation report not found: {REPORT_FILE.name}",
        )

    try:
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail="evaluation report is not valid JSON",
        ) from exc

    if not isinstance(report, dict):
        raise HTTPException(
            status_code=500,
            detail="evaluation report must be a JSON object",
        )

    report.setdefault("source", str(REPORT_FILE.relative_to(PROJECT_ROOT)))
    return report
