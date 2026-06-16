"""Fix mypy object-iterable errors in targeted parser workflow regression."""

from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Final

BACKEND_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CHECK_FILE: Final[Path] = (
    BACKEND_ROOT / "scripts/check_phase3ii_targeted_parser_workflow_regression.py"
)


def main() -> int:
    """Patch object iterable access."""

    print("=" * 80)
    print("fixing targeted parser workflow regression mypy errors")

    if not CHECK_FILE.exists():
        pprint({"error": f"missing check file: {CHECK_FILE}"})
        return 1

    content = CHECK_FILE.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    old_any = '    must_contain_any = tuple(str(item) for item in case["must_contain_any"])\n'
    new_any = '    must_contain_any = as_tuple(case.get("must_contain_any"))\n'

    old_not = '    must_not_contain = tuple(str(item) for item in case["must_not_contain"])\n'
    new_not = '    must_not_contain = as_tuple(case.get("must_not_contain"))\n'

    if old_any in content:
        content = content.replace(old_any, new_any, 1)
        changes.append("patched must_contain_any")
    elif new_any in content:
        changes.append("must_contain_any already patched")
    else:
        pprint({"error": "must_contain_any anchor not found"})
        return 1

    if old_not in content:
        content = content.replace(old_not, new_not, 1)
        changes.append("patched must_not_contain")
    elif new_not in content:
        changes.append("must_not_contain already patched")
    else:
        pprint({"error": "must_not_contain anchor not found"})
        return 1

    helper_block = '''
def as_tuple(
    value: object,
) -> tuple[str, ...]:
    """Convert tuple/list/scalar value to tuple[str, ...]."""

    if value is None:
        return ()

    if isinstance(value, tuple):
        return tuple(str(item) for item in value)

    if isinstance(value, list):
        return tuple(str(item) for item in value)

    return (str(value),)
'''

    if "def as_tuple(" not in content:
        insert_anchor = "\ndef configure_no_real_llm_mode() -> None:\n"

        if insert_anchor not in content:
            pprint({"error": "as_tuple insertion anchor not found"})
            return 1

        content = content.replace(
            insert_anchor,
            "\n" + helper_block.strip() + "\n\n\n" + "def configure_no_real_llm_mode() -> None:\n",
            1,
        )
        changes.append("inserted as_tuple helper")
    else:
        changes.append("as_tuple helper already exists")

    if content != original:
        CHECK_FILE.write_text(content, encoding="utf-8")

    pprint(
        {
            "check_file": str(CHECK_FILE),
            "changed": content != original,
            "changes": changes,
        }
    )

    print("targeted parser workflow regression mypy fix completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())