"""Patch openpyxl imports for mypy import-untyped."""

from __future__ import annotations

from pathlib import Path


target = Path("scripts/check_quality_questions_file.py")
content = target.read_text(encoding="utf-8")

content = content.replace(
    "from openpyxl import load_workbook\n",
    "from openpyxl import load_workbook  # type: ignore[import-untyped]\n",
)

content = content.replace(
    "from openpyxl.worksheet.worksheet import Worksheet\n",
    "from openpyxl.worksheet.worksheet import Worksheet  # type: ignore[import-untyped]\n",
)

target.write_text(content, encoding="utf-8")

print("patched openpyxl imports for mypy")