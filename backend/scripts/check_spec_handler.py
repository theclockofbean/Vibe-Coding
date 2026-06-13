"""Check SpecHandler structured handler results.

This script only reads from PostgreSQL. It does not modify data.
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.handlers import SpecHandler, SpecHandlerInput  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


def main() -> int:
    """Run handler smoke checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ProductRepository(session)
        service = SpecQueryService(repository)
        handler = SpecHandler(service)

        sku_result = handler.handle(
            SpecHandlerInput(
                query_type="sku_id",
                query_value="sku001",
            )
        )
        print("sku_id result:")
        pprint(sku_result.to_dict())

        if sku_result.status != "success" or sku_result.matched_count != 1:
            print("failed: sku001 should return success with one match")
            return 1

        thread_result = handler.handle(
            SpecHandlerInput(
                query_type="thread_spec",
                query_value="M8x1.25",
                limit=5,
            )
        )
        print("\nthread_spec result:")
        pprint(thread_result.to_dict())

        if thread_result.status != "success" or thread_result.matched_count == 0:
            print("failed: thread spec should return products")
            return 1

        oem_result = handler.handle(
            SpecHandlerInput(
                query_type="oem_reference_number",
                query_value="43330-39585",
            )
        )
        print("\noem result:")
        pprint(oem_result.to_dict())

        if oem_result.status != "success" or oem_result.matched_count != 1:
            print("failed: OEM should return success with one match")
            return 1

        dimension_result = handler.handle(
            SpecHandlerInput(
                query_type="thread_dimensions",
                diameter_mm="8",
                pitch_mm="1.25",
                limit=5,
            )
        )
        print("\nthread_dimensions result:")
        pprint(dimension_result.to_dict())

        if dimension_result.status != "success":
            print("failed: thread dimensions should return success")
            return 1

        missing_result = handler.handle(
            SpecHandlerInput(
                query_type="sku_id",
                query_value="SKU999",
            )
        )
        print("\nmissing sku result:")
        pprint(missing_result.to_dict())

        if missing_result.status != "not_found":
            print("failed: missing SKU should return not_found")
            return 1

        invalid_result = handler.handle(
            SpecHandlerInput(
                query_type="thread_dimensions",
                diameter_mm="abc",
                pitch_mm="1.25",
            )
        )
        print("\ninvalid request result:")
        pprint(invalid_result.to_dict())

        if invalid_result.status != "invalid_request":
            print("failed: invalid dimensions should return invalid_request")
            return 1

        if invalid_result.handoff_required:
            print("failed: invalid request should not force handoff here")
            return 1

    print("\nspec handler check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())