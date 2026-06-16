"""Reproduce spec workflow handler failure with one SKU query."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Final

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.workflow import run_agent_workflow
from app.core.config import settings
from app.repositories import ProductRepository

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
OUTPUT_FILE: Final[Path] = PROJECT_ROOT / "logs/diagnostics/phase3ii_spec_workflow_handler_failure_repro.json"


def main() -> int:
    """Run one workflow case and export state/error."""

    query = "SKU001铝合金竞技换挡球头的螺纹规格是多少"

    result: dict[str, Any] = {
        "query": query,
        "error": None,
        "traceback": None,
        "state": None,
    }

    try:
        engine = create_engine(settings.database_url)
        session_factory = sessionmaker(bind=engine)

        with session_factory() as session:
            repository = ProductRepository(session)
            state = run_agent_workflow(
                initial_state={
                    "user_message": query,
                    "messages": [],
                },
                product_repository=repository,
                limit=5,
            )
            result["state"] = shorten(state)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print("=" * 80)
    print("spec workflow handler failure repro exported")
    print(f"output_file: {OUTPUT_FILE}")
    print(f"error: {result['error']}")
    return 0


def shorten(value: Any, *, limit: int = 2000) -> Any:
    """Shorten nested values."""

    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "...<truncated>"

    if isinstance(value, list):
        return [shorten(item, limit=limit) for item in value[:30]]

    if isinstance(value, dict):
        return {
            str(key): shorten(item, limit=limit)
            for key, item in list(value.items())[:120]
        }

    return value


if __name__ == "__main__":
    raise SystemExit(main())