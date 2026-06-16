"""Check spec parser structured query coverage."""

from __future__ import annotations

from pprint import pprint
from typing import Any, Final, NamedTuple

from app.agent.parsers.spec_parameter_parser import SpecParameterParser


class Case(NamedTuple):
    """Parser check case."""

    query: str
    expected_query_type: str
    expected_query_value: str | None
    expected_diameter_mm: str | None


CASES: Final[tuple[Case, ...]] = (
    Case(
        query="我想要M12螺纹的球头 你们有哪几款",
        expected_query_type="thread_diameter",
        expected_query_value=None,
        expected_diameter_mm="12",
    ),
    Case(
        query="你们钛合金材质的球头有哪些款",
        expected_query_type="material_keyword",
        expected_query_value="钛合金",
        expected_diameter_mm=None,
    ),
    Case(
        query="碳纤维材质的球头螺纹规格有几种",
        expected_query_type="material_keyword",
        expected_query_value="碳纤维",
        expected_diameter_mm=None,
    ),
    Case(
        query="你们最长的杆是多少 哪款",
        expected_query_type="max_rod_length",
        expected_query_value=None,
        expected_diameter_mm=None,
    ),
    Case(
        query="球径最大的球头是哪款",
        expected_query_type="max_ball_diameter",
        expected_query_value=None,
        expected_diameter_mm=None,
    ),
)


def main() -> int:
    """Run parser targeted checks."""

    print("=" * 80)
    print("checking Phase 3-I-I spec parser structured queries")

    parser = SpecParameterParser()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for case in CASES:
        parsed = parser.parse(case.query)

        row = {
            "query": case.query,
            "expected_query_type": case.expected_query_type,
            "actual_query_type": parsed.query_type,
            "expected_query_value": case.expected_query_value,
            "actual_query_value": parsed.query_value,
            "expected_diameter_mm": case.expected_diameter_mm,
            "actual_diameter_mm": parsed.diameter_mm,
            "status": parsed.status,
            "errors": parsed.errors,
        }
        rows.append(row)

        if parsed.query_type != case.expected_query_type:
            errors.append(
                f"{case.query}: expected query_type {case.expected_query_type}, "
                f"got {parsed.query_type}"
            )

        if parsed.query_value != case.expected_query_value:
            errors.append(
                f"{case.query}: expected query_value {case.expected_query_value}, "
                f"got {parsed.query_value}"
            )

        if parsed.diameter_mm != case.expected_diameter_mm:
            errors.append(
                f"{case.query}: expected diameter_mm {case.expected_diameter_mm}, "
                f"got {parsed.diameter_mm}"
            )

    pprint({"rows": rows, "errors": errors})

    if errors:
        print("Phase 3-I-I spec parser structured query check failed")
        return 1

    print("Phase 3-I-I spec parser structured query check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())