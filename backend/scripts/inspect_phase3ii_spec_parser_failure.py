"""Source-only inspection for Phase 3-I-I parser SKU boundary issues."""

from __future__ import annotations

import re
from pathlib import Path
from pprint import pprint
from typing import Any, Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

PARSER_FILES: Final[dict[str, Path]] = {
    "spec": BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py",
    "price": BACKEND_ROOT / "app/agent/parsers/price_parameter_parser.py",
    "quality": BACKEND_ROOT / "app/agent/parsers/quality_parameter_parser.py",
    "logistics": BACKEND_ROOT / "app/agent/parsers/logistics_parameter_parser.py",
}

SAMPLES: Final[tuple[str, ...]] = (
    "SKU001铝合金竞技换挡球头的螺纹规格是多少",
    "SKU002碳纤维的杆长是多少毫米",
    "SKU003真皮那款有锥度要求吗 怎么安装",
    "SKU004不锈钢子弹头 给我报一下全部参数",
    "sku25夜光全透明球头杆长多少",
    "SKU-7是什么螺纹",
    "SKU 8是什么规格",
    "XS-SKU001A不是合法SKU边界",
)

EXPECTED_SAFE_SPEC_PATTERN: Final[str] = (
    r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])"
)

REFERENCE_REGEXES: Final[dict[str, str]] = {
    "old_word_boundary": r"\bSKU[-_\s]?(?P<number>\d{1,3})\b",
    "safe_ascii_boundary": EXPECTED_SAFE_SPEC_PATTERN,
    "logistics_safe": r"(?<![A-Za-z0-9])SKU\s*0*(\d{1,3})(?![A-Za-z0-9])",
}


def main() -> int:
    """Run source-only parser boundary inspection."""

    print("=" * 80)
    print("inspecting Phase 3-I-I parser SKU boundary by source only")

    parser_source_result = inspect_parser_sources()
    reference_regex_result = test_reference_regexes()

    result = {
        "parser_source_result": parser_source_result,
        "reference_regex_result": reference_regex_result,
    }

    pprint(result)

    print("Phase 3-I-I parser SKU boundary source inspection completed")
    return 0


def inspect_parser_sources() -> dict[str, Any]:
    """Inspect parser source files without importing app modules."""

    result: dict[str, Any] = {}

    for name, path in PARSER_FILES.items():
        if not path.exists():
            result[name] = {
                "exists": False,
                "path": str(path),
            }
            continue

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        sku_pattern_lines = [
            f"{line_number}: {line.strip()}"
            for line_number, line in enumerate(lines, start=1)
            if "SKU_PATTERN" in line
            or "SKU" in line and "re.compile" in line
            or "SKU" in line and "\\b" in line
            or "SKU" in line and "?<!" in line
        ]

        result[name] = {
            "exists": True,
            "path": str(path.relative_to(BACKEND_ROOT)),
            "has_old_word_boundary": "\\bSKU" in content,
            "has_safe_ascii_boundary": "(?<![A-Za-z0-9])SKU" in content,
            "has_expected_safe_spec_pattern": EXPECTED_SAFE_SPEC_PATTERN in content,
            "sku_pattern_lines": sku_pattern_lines[:20],
        }

    return result


def test_reference_regexes() -> dict[str, Any]:
    """Compare old and safe SKU regex behavior."""

    result: dict[str, Any] = {}

    for name, pattern in REFERENCE_REGEXES.items():
        regex = re.compile(pattern, flags=re.IGNORECASE)
        result[name] = {
            sample: extract_skus(regex=regex, text=sample)
            for sample in SAMPLES
        }

    return result


def extract_skus(
    *,
    regex: re.Pattern[str],
    text: str,
) -> list[str]:
    """Extract normalized SKU IDs from regex matches."""

    sku_ids: list[str] = []

    for match in regex.finditer(text):
        if "number" in regex.groupindex:
            raw_number = match.group("number")
        else:
            raw_number = match.group(1)

        try:
            number = int(raw_number)
        except ValueError:
            continue

        sku_id = f"SKU{number:03d}"

        if sku_id not in sku_ids:
            sku_ids.append(sku_id)

    return sku_ids


if __name__ == "__main__":
    raise SystemExit(main())