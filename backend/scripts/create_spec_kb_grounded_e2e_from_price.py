"""Create Spec KB grounded E2E check from passed Price KB E2E script."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SOURCE_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_price_kb_grounded_e2e.py"
TARGET_FILE: Final[Path] = BACKEND_ROOT / "scripts/check_spec_kb_grounded_e2e.py"


SPEC_TEST_CASES_BLOCK: Final[str] = '''TEST_CASES: Final[tuple[dict[str, str], ...]] = (
    {
        "case_id": "SPEC_E2E_001",
        "query": "SKU001是什么规格？",
    },
    {
        "case_id": "SPEC_E2E_002",
        "query": "SKU001的螺纹规格是多少？",
    },
    {
        "case_id": "SPEC_E2E_003",
        "query": "M10的球头有哪些？",
    },
    {
        "case_id": "SPEC_E2E_004",
        "query": "杆长120mm有吗？",
    },
    {
        "case_id": "SPEC_E2E_005",
        "query": "这个球头能通用适配吗？",
    },
)
'''


SPEC_FORBIDDEN_RESPONSE_FRAGMENTS_BLOCK: Final[str] = '''FORBIDDEN_RESPONSE_FRAGMENTS: Final[tuple[str, ...]] = (
    "万能适配",
    "百分百适配",
    "一定适配",
    "保证适配",
    "全部车型都能用",
    "不用核对直接能用",
)
'''


def main() -> int:
    """Create Spec E2E script."""

    print("=" * 80)
    print("creating Spec KB grounded E2E script from Price KB E2E script")

    if not SOURCE_FILE.exists():
        pprint({"error": f"missing source file: {SOURCE_FILE}"})
        return 1

    content = SOURCE_FILE.read_text(encoding="utf-8")

    replacements = [
        ("Price KB", "Spec KB"),
        ("price KB", "spec KB"),
        ("PRICE_KB", "SPEC_KB"),
        ("QDRANT_COLLECTION_PRICE", "QDRANT_COLLECTION_SPEC"),
        ("PRICE_KB_RETRIEVER_ENABLED", "SPEC_KB_RETRIEVER_ENABLED"),
        ("PRICE_KB_COLLECTION_NAME", "SPEC_KB_COLLECTION_NAME"),
        ("PRICE_KB_TOP_K", "SPEC_KB_TOP_K"),
        ("price_kb_v1", "spec_kb_v1"),
        ("real_price_kb", "real_spec_kb"),
        ("real_price_kb_retriever", "real_spec_kb_retriever"),
        ("price_qa_price", "spec_qa_spec"),
        ("PRICE_E2E", "SPEC_E2E"),
        ("price", "spec"),
        ("Price", "Spec"),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    content = replace_assignment_block(
        content=content,
        variable_name="TEST_CASES",
        replacement=SPEC_TEST_CASES_BLOCK,
    )

    if "FORBIDDEN_RESPONSE_FRAGMENTS" in content:
        content = replace_assignment_block(
            content=content,
            variable_name="FORBIDDEN_RESPONSE_FRAGMENTS",
            replacement=SPEC_FORBIDDEN_RESPONSE_FRAGMENTS_BLOCK,
        )

    required_fragments = [
        "SPEC_E2E_001",
        "spec_kb_v1",
        "real_spec_kb",
        "real_spec_kb_retriever",
    ]

    forbidden_fragments = [
        "PRICE_E2E",
        "price_kb_v1",
        "real_price_kb",
        "PRICE_KB",
    ]

    missing = [
        fragment
        for fragment in required_fragments
        if fragment not in content
    ]

    leftovers = [
        fragment
        for fragment in forbidden_fragments
        if fragment in content
    ]

    if missing or leftovers:
        pprint(
            {
                "error": "generated script validation failed",
                "missing": missing,
                "leftovers": leftovers,
            }
        )
        return 1

    TARGET_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "source_file": str(SOURCE_FILE),
            "target_file": str(TARGET_FILE),
            "created": True,
        }
    )

    print("Spec KB grounded E2E script created")
    return 0


def replace_assignment_block(
    *,
    content: str,
    variable_name: str,
    replacement: str,
) -> str:
    """Replace a top-level assignment block."""

    lines = content.splitlines(keepends=True)

    start_index = find_assignment_start(lines=lines, variable_name=variable_name)
    end_index = find_assignment_end(lines=lines, start_index=start_index)

    replacement_lines = replacement.rstrip().splitlines(keepends=False)
    replacement_text_lines = [f"{line}\n" for line in replacement_lines]

    new_lines = (
        lines[:start_index]
        + replacement_text_lines
        + ["\n"]
        + lines[end_index:]
    )

    return "".join(new_lines)


def find_assignment_start(
    *,
    lines: list[str],
    variable_name: str,
) -> int:
    """Find assignment start line."""

    prefix = f"{variable_name}:"

    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index

    raise ValueError(f"missing assignment: {variable_name}")


def find_assignment_end(
    *,
    lines: list[str],
    start_index: int,
) -> int:
    """Find assignment end by bracket depth."""

    depth = 0
    seen_value_container = False

    for index in range(start_index, len(lines)):
        line = lines[index]

        for char in line:
            if char in "([{":
                depth += 1
                seen_value_container = True
            elif char in ")]}":
                depth -= 1

        if seen_value_container and depth == 0 and index > start_index:
            return index + 1

    raise ValueError("unterminated assignment block")


if __name__ == "__main__":
    raise SystemExit(main())