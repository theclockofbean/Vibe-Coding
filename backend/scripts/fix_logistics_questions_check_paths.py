"""Fix logistics questions check script file paths."""

from __future__ import annotations

from pathlib import Path


CHECK_FILE = Path("scripts/check_logistics_questions_file.py")


def main() -> int:
    """Patch logistics and SKU master file paths."""

    content = CHECK_FILE.read_text(encoding="utf-8")

    old_logistics = '''LOGISTICS_FILE: Final[Path] = (
    PROJECT_ROOT / "data" / "uploads" / "qa_pairs" / "logistics_questions.xlsx"
)
'''

    new_logistics = '''LOGISTICS_FILE: Final[Path] = (
    PROJECT_ROOT
    / "data"
    / "uploads"
    / "conversations"
    / "qa_pairs_raw"
    / "logistics_questions.xlsx"
)
'''

    old_sku = '''SKU_MASTER_FILE: Final[Path] = PROJECT_ROOT / "data" / "uploads" / "sku_master.xlsx"
'''

    new_sku = '''SKU_MASTER_FILE: Final[Path] = (
    PROJECT_ROOT / "data" / "uploads" / "specs" / "sku_master.xlsx"
)
'''

    if old_logistics not in content:
        raise RuntimeError("old logistics path block not found")

    if old_sku not in content:
        raise RuntimeError("old sku master path line not found")

    content = content.replace(old_logistics, new_logistics, 1)
    content = content.replace(old_sku, new_sku, 1)

    CHECK_FILE.write_text(content, encoding="utf-8")

    print("logistics questions check paths fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())