"""Check ProductRepository read methods.

This script only reads from PostgreSQL. It does not modify data.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory  # noqa: E402
from app.repositories import ProductRepository  # noqa: E402


def main() -> int:
    """Run repository smoke checks."""

    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ProductRepository(session)

        active_count = repository.count_active_products()
        print("active_count:")
        print(active_count)

        if active_count != 100:
            print("failed: active product count is not 100")
            return 1

        sku001 = repository.get_by_sku_id("SKU001")
        print("\nSKU001:")
        print(
            None
            if sku001 is None
            else {
                "sku_id": sku001.sku_id,
                "product_name": sku001.product_name,
                "thread_spec": sku001.thread_spec,
                "rod_length_mm": str(sku001.rod_length_mm),
                "ball_diameter_mm": str(sku001.ball_diameter_mm),
                "taper_ratio": sku001.taper_ratio,
                "oem_reference_number": sku001.oem_reference_number,
            }
        )

        if sku001 is None:
            print("failed: SKU001 not found")
            return 1

        oem_product = repository.get_by_oem_reference("43330-39585")
        print("\nOEM 43330-39585:")
        print(None if oem_product is None else oem_product.sku_id)

        if oem_product is None or oem_product.sku_id != "SKU001":
            print("failed: OEM lookup mismatch")
            return 1

        m8_products = repository.list_by_thread_spec("M8×1.25", limit=5)
        print("\nfirst 5 M8x1.25 products:")
        print([product.sku_id for product in m8_products])

        if not m8_products:
            print("failed: M8 thread lookup returned empty list")
            return 1

        dimension_products = repository.list_by_thread_dimensions(
            diameter_mm=Decimal("8"),
            pitch_mm=Decimal("1.25"),
            limit=5,
        )
        print("\nfirst 5 M8/1.25 dimension products:")
        print([product.sku_id for product in dimension_products])

        if not dimension_products:
            print("failed: dimension lookup returned empty list")
            return 1

        missing_product = repository.get_by_sku_id("SKU999")
        print("\nSKU999:")
        print(missing_product)

        if missing_product is not None:
            print("failed: missing SKU lookup should return None")
            return 1

    print("\nproduct repository check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())