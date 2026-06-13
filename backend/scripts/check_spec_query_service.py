"""Check SpecQueryService structured query methods.

This script only reads from PostgreSQL. It does not modify data.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402
from app.services import SpecQueryService  # noqa: E402


def main() -> int:
    """Run service smoke checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ProductRepository(session)
        service = SpecQueryService(repository)

        sku_result = service.query_by_sku("sku001")
        print("query_by_sku sku001:")
        pprint(sku_result.to_dict())

        if sku_result.matched_count != 1:
            print("failed: sku001 should match exactly one product")
            return 1

        oem_result = service.query_by_oem_reference("43330-39585")
        print("\nquery_by_oem_reference 43330-39585:")
        pprint(oem_result.to_dict())

        if oem_result.matched_count != 1:
            print("failed: OEM should match exactly one product")
            return 1

        thread_result = service.query_by_thread_spec("M8x1.25", limit=5)
        print("\nquery_by_thread_spec M8x1.25:")
        pprint(thread_result.to_dict())

        if thread_result.query_value != "M8×1.25":
            print("failed: thread spec was not normalized")
            return 1

        if thread_result.matched_count == 0:
            print("failed: thread spec should return products")
            return 1

        dimension_result = service.query_by_thread_dimensions(
            diameter_mm=Decimal("8"),
            pitch_mm=Decimal("1.25"),
            limit=5,
        )
        print("\nquery_by_thread_dimensions M8/1.25:")
        pprint(dimension_result.to_dict())

        if dimension_result.matched_count == 0:
            print("failed: thread dimensions should return products")
            return 1

        missing_result = service.query_by_sku("SKU999")
        print("\nquery_by_sku SKU999:")
        pprint(missing_result.to_dict())

        if missing_result.matched_count != 0:
            print("failed: missing SKU should return zero products")
            return 1

        if missing_result.handoff_required:
            print("failed: missing spec query should not force handoff here")
            return 1

    print("\nspec query service check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())