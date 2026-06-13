"""Import validated sku_master.xlsx into PostgreSQL.

This script validates the Excel file first. Only when validation passes will it
insert one import batch and all product rows in a single transaction.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from sqlalchemy import func, select

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory  # noqa: E402
from app.models.import_batch import DataImportBatch  # noqa: E402
from app.models.product import Product  # noqa: E402
from scripts.validate_sku_master import (  # noqa: E402
    PROJECT_ROOT,
    SKU_FILE,
    ValidatedSkuRow,
    validate_sku_file,
)

DATA_TYPE: Final[str] = "sku_master"
ACTIVE_BATCH_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "running",
    "success",
    "partial_success",
)


def calculate_sha256(path: Path) -> str:
    """Return SHA256 hex digest for a file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def to_relative_path(path: Path) -> str:
    """Return a project-relative path when possible."""

    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def build_product(row: ValidatedSkuRow, *, import_batch_id: int) -> Product:
    """Build a Product ORM object from one validated SKU row."""

    return Product(
        sku_id=row.sku_id,
        product_name=row.product_name,
        thread_spec=row.thread_spec,
        thread_type="M",
        thread_diameter_mm=row.thread_diameter_mm,
        thread_pitch_mm=row.thread_pitch_mm,
        rod_length_mm=row.rod_length_mm,
        ball_diameter_mm=row.ball_diameter_mm,
        taper_ratio=row.taper_ratio,
        material=row.material,
        surface_treatment=row.surface_treatment,
        oem_reference_number=row.oem_reference_number,
        min_order_qty=row.min_order_qty,
        stock_status=row.stock_status,
        lead_time_days=row.lead_time_days,
        is_active=True,
        import_batch_id=import_batch_id,
        source_file=to_relative_path(SKU_FILE),
        source_row_number=row.excel_row_number,
    )


def ensure_source_not_imported(source_sha256: str) -> None:
    """Reject duplicate active or successful imports of the same source file."""

    session_factory = get_session_factory()

    with session_factory() as session:
        existing_batch_id = session.execute(
            select(DataImportBatch.batch_id).where(
                DataImportBatch.data_type == DATA_TYPE,
                DataImportBatch.source_sha256 == source_sha256,
                DataImportBatch.status.in_(ACTIVE_BATCH_STATUSES),
            )
        ).scalar_one_or_none()

    if existing_batch_id is not None:
        raise RuntimeError(
            "same sku_master source file has already been imported "
            f"or is active: batch_id={existing_batch_id}"
        )


def ensure_products_table_empty() -> None:
    """Reject import when products already contains rows."""

    session_factory = get_session_factory()

    with session_factory() as session:
        product_count = session.execute(
            select(func.count()).select_from(Product)
        ).scalar_one()

    if product_count > 0:
        raise RuntimeError(
            "products table is not empty. This first importer only supports "
            "initial load; re-import/update will be implemented separately."
        )


def import_rows(rows: list[ValidatedSkuRow], *, source_sha256: str) -> int:
    """Insert one import batch and all product rows transactionally."""

    session_factory = get_session_factory()
    now = datetime.now(UTC)

    with session_factory() as session:
        try:
            batch = DataImportBatch(
                data_type=DATA_TYPE,
                source_file=SKU_FILE.name,
                source_path=to_relative_path(SKU_FILE),
                source_sha256=source_sha256,
                record_count=len(rows),
                success_count=0,
                failed_count=0,
                status="running",
                started_at=now,
            )
            session.add(batch)
            session.flush()

            if batch.id is None:
                raise RuntimeError("failed to create import batch id")

            products = [
                build_product(row, import_batch_id=batch.id)
                for row in rows
            ]

            session.add_all(products)

            batch.success_count = len(rows)
            batch.failed_count = 0
            batch.status = "success"
            batch.finished_at = datetime.now(UTC)

            session.commit()
            return int(batch.id)

        except Exception:
            session.rollback()
            raise


def main() -> int:
    """Validate and import sku_master.xlsx."""

    print("sku import started")
    print(f"source_file: {SKU_FILE}")

    rows, validation_errors = validate_sku_file(SKU_FILE)

    if validation_errors:
        print("sku import stopped: validation failed")
        for error in validation_errors:
            print(f"- {error}")

        return 1

    source_sha256 = calculate_sha256(SKU_FILE)

    print(f"validated_rows: {len(rows)}")
    print(f"source_sha256: {source_sha256}")

    try:
        ensure_source_not_imported(source_sha256)
        ensure_products_table_empty()
        batch_id = import_rows(rows, source_sha256=source_sha256)
    except Exception as exc:
        print("sku import failed")
        print(f"- {exc}")
        return 1

    print("sku import passed")
    print(f"import_batch_id: {batch_id}")
    print(f"inserted_products: {len(rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())