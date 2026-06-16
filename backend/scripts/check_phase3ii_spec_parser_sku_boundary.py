"""Check SpecParameterParser SKU regex supports Chinese-adjacent SKU text."""

from __future__ import annotations

import re
from pathlib import Path
from pprint import pprint
from typing import Any, Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SPEC_PARSER_FILE: Final[Path] = (
    BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py"
)

EXPECTED_PATTERN_FRAGMENT: Final[str] = (
    r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])"
)

SAMPLE_EXPECTATIONS: Final[tuple[tuple[str, list[str]], ...]] = (
    ("SKU001铝合金竞技换挡球头的螺纹规格是多少", ["SKU001"]),
    ("SKU002碳纤维的杆长是多少毫米", ["SKU002"]),
    ("SKU003真皮那款有锥度要求吗 怎么安装", ["SKU003"]),
    ("SKU004不锈钢子弹头 给我报一下全部参数", ["SKU004"]),
    ("sku25夜光全透明球头杆长多少", ["SKU025"]),
    ("SKU-7是什么螺纹", ["SKU007"]),
    ("SKU 8是什么规格", ["SKU008"]),
    ("XS-SKU001A不是合法SKU边界", []),
)


def main() -> int:
    """Run source-level SKU boundary regression."""

    print("=" * 80)
    print("checking Phase 3-I-I spec parser SKU boundary")

    errors: list[str] = []

    if not SPEC_PARSER_FILE.exists():
        errors.append(f"missing parser file: {SPEC_PARSER_FILE}")
        pprint({"errors": errors})
        return 1

    content = SPEC_PARSER_FILE.read_text(encoding="utf-8")

    if EXPECTED_PATTERN_FRAGMENT not in content:
        errors.append(
            "SpecParameterParser SKU_PATTERN does not contain expected "
            "Chinese-adjacent-safe boundary regex"
        )

    regex = re.compile(EXPECTED_PATTERN_FRAGMENT, flags=re.IGNORECASE)
    sample_results: list[dict[str, Any]] = []

    for query, expected_skus in SAMPLE_EXPECTATIONS:
        actual_skus = extract_sku_ids(regex=regex, text=query)

        if actual_skus != expected_skus:
            errors.append(
                f"{query}: expected {expected_skus}, got {actual_skus}"
            )

        sample_results.append(
            {
                "query": query,
                "expected_skus": expected_skus,
                "actual_skus": actual_skus,
            }
        )

    pprint(
        {
            "parser_file": str(SPEC_PARSER_FILE),
            "expected_pattern_fragment": EXPECTED_PATTERN_FRAGMENT,
            "sample_results": sample_results,
            "errors": errors,
        }
    )

    if errors:
        print("Phase 3-I-I spec parser SKU boundary check failed")
        return 1

    print("Phase 3-I-I spec parser SKU boundary check passed")
    return 0


def extract_sku_ids(
    *,
    regex: re.Pattern[str],
    text: str,
) -> list[str]:
    """Extract canonical SKU IDs using the target regex."""

    sku_ids: list[str] = []

    for match in regex.finditer(text):
        number = int(match.group("number"))
        sku_id = f"SKU{number:03d}"

        if sku_id not in sku_ids:
            sku_ids.append(sku_id)

    return sku_ids


if __name__ == "__main__":
    raise SystemExit(main())