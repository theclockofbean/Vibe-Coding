"""Source-only regression for SKU boundary regex across four parsers."""

from __future__ import annotations

import re
from pathlib import Path
from pprint import pprint
from typing import Any, Final


BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

PARSER_EXPECTATIONS: Final[dict[str, dict[str, object]]] = {
    "spec": {
        "file": BACKEND_ROOT / "app/agent/parsers/spec_parameter_parser.py",
        "pattern": r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])",
        "must_contain": "(?<![A-Za-z0-9])SKU[-_\\s]?",
        "must_not_contain": r"\bSKU[-_\s]?",
        "samples": {
            "SKU001铝合金竞技换挡球头的螺纹规格是多少": ["SKU001"],
            "SKU002碳纤维的杆长是多少毫米": ["SKU002"],
            "sku25夜光全透明球头杆长多少": ["SKU025"],
            "SKU-7是什么螺纹": ["SKU007"],
            "SKU 8是什么规格": ["SKU008"],
            "XS-SKU001A不是合法SKU边界": [],
        },
    },
    "price": {
        "file": BACKEND_ROOT / "app/agent/parsers/price_parameter_parser.py",
        "pattern": r"(?<![A-Za-z0-9])SKU[-_\s]?(?P<number>\d{1,3})(?![A-Za-z0-9])",
        "must_contain": "(?<![A-Za-z0-9])SKU[-_\\s]?",
        "must_not_contain": r"\bSKU[-_\s]?",
        "samples": {
            "SKU001多少钱一个": ["SKU001"],
            "SKU032价格368元 能便宜点吗": ["SKU032"],
            "sku25能不能优惠": ["SKU025"],
            "SKU-7报价多少": ["SKU007"],
            "SKU 8批发价": ["SKU008"],
            "XS-SKU001A不是合法SKU边界": [],
        },
    },
    "quality": {
        "file": BACKEND_ROOT / "app/agent/parsers/quality_parameter_parser.py",
        "pattern": r"(?<![A-Za-z0-9])SKU\d{3,}(?![A-Za-z0-9])",
        "must_contain": "(?<![A-Za-z0-9])SKU\\d{3,}",
        "must_not_contain": r"\bSKU\d{3,}\b",
        "samples": {
            "SKU001夏天暴晒后会不会烫手": ["SKU001"],
            "SKU004会不会生锈": ["SKU004"],
            "SKU041迷彩图案会不会褪色": ["SKU041"],
            "sku005夜光会不会越用越暗": ["SKU005"],
            "XS-SKU001A不是合法SKU边界": [],
        },
    },
    "logistics": {
        "file": BACKEND_ROOT / "app/agent/parsers/logistics_parameter_parser.py",
        "pattern": r"(?<![A-Za-z0-9])SKU\s*0*(\d{1,3})(?![A-Za-z0-9])",
        "must_contain": "(?<![A-Za-z0-9])SKU\\s*0*",
        "must_not_contain": r"\bSKU",
        "samples": {
            "SKU001什么时候发货": ["SKU001"],
            "SKU020发北京预计多久": ["SKU020"],
            "sku25能发货吗": ["SKU025"],
            "SKU 8是什么物流": ["SKU008"],
            "XS-SKU001A不是合法SKU边界": [],
        },
    },
}


def main() -> int:
    """Run four-parser SKU boundary regression."""

    print("=" * 80)
    print("checking Phase 3-I-I four parser SKU boundary regression")

    errors: list[str] = []
    results: dict[str, Any] = {}

    for module_name, expectation in PARSER_EXPECTATIONS.items():
        module_result = check_one_module(
            module_name=module_name,
            expectation=expectation,
            errors=errors,
        )
        results[module_name] = module_result

    pprint(
        {
            "results": results,
            "errors": errors,
        }
    )

    if errors:
        print("Phase 3-I-I four parser SKU boundary regression failed")
        return 1

    print("Phase 3-I-I four parser SKU boundary regression passed")
    return 0


def check_one_module(
    *,
    module_name: str,
    expectation: dict[str, object],
    errors: list[str],
) -> dict[str, Any]:
    """Check one parser source and regex behavior."""

    file_path = expectation["file"]

    if not isinstance(file_path, Path):
        errors.append(f"{module_name}: invalid file path")
        return {"error": "invalid file path"}

    if not file_path.exists():
        errors.append(f"{module_name}: missing parser file: {file_path}")
        return {"exists": False, "path": str(file_path)}

    content = file_path.read_text(encoding="utf-8")
    must_contain = str(expectation["must_contain"])
    must_not_contain = str(expectation["must_not_contain"])
    pattern = str(expectation["pattern"])
    samples = expectation["samples"]

    if not isinstance(samples, dict):
        errors.append(f"{module_name}: samples must be dict")
        samples = {}

    source_errors: list[str] = []

    if must_contain not in content:
        source_errors.append(f"missing safe pattern fragment: {must_contain}")

    if must_not_contain in content:
        source_errors.append(f"old unsafe word-boundary pattern still exists: {must_not_contain}")

    regex = re.compile(pattern, flags=re.IGNORECASE)
    sample_results: list[dict[str, object]] = []

    for query, expected_value in samples.items():
        expected_skus = [str(item) for item in expected_value]
        actual_skus = extract_skus(regex=regex, text=str(query), module_name=module_name)

        if actual_skus != expected_skus:
            source_errors.append(
                f"{query}: expected {expected_skus}, got {actual_skus}"
            )

        sample_results.append(
            {
                "query": query,
                "expected_skus": expected_skus,
                "actual_skus": actual_skus,
            }
        )

    for error in source_errors:
        errors.append(f"{module_name}: {error}")

    return {
        "path": str(file_path.relative_to(BACKEND_ROOT)),
        "safe_pattern_fragment_found": must_contain in content,
        "old_pattern_absent": must_not_contain not in content,
        "sample_results": sample_results,
        "errors": source_errors,
    }


def extract_skus(
    *,
    regex: re.Pattern[str],
    text: str,
    module_name: str,
) -> list[str]:
    """Extract normalized SKU IDs from regex matches."""

    sku_ids: list[str] = []

    for match in regex.finditer(text):
        if "number" in regex.groupindex:
            raw_number = match.group("number")
        elif module_name == "quality":
            matched_text = match.group(0)
            raw_number = re.sub(r"(?i)^SKU", "", matched_text)
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